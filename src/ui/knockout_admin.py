# src/ui/knockout_admin.py
#
# Admin-UI för slutspelstipset.
#
# Första versionen visar bara rundor och låter admin uppdatera
# deadline/status. Matchinmatning kommer i nästa pass.

from datetime import date, time

import pandas as pd
import streamlit as st

from src.deadline import (
    build_deadline_iso_from_swedish_time,
)

from src.repositories.knockout_repo import (
    clear_knockout_match_result,
    get_knockout_matches,
    get_knockout_round_by_name,
    get_knockout_rounds,
    update_knockout_match_result,
    update_knockout_round,
    upsert_knockout_match,
)

from src.time_utils import format_datetime_swedish

from src.ui.knockout_leaderboard import render_knockout_leaderboard_section

def render_knockout_matches_table() -> None:
    """
    Visar alla slutspelsmatcher som finns i databasen.

    Matcherna läggs in manuellt av admin.
    """

    matches = get_knockout_matches()

    if not matches:
        st.info("Inga slutspelsmatcher finns ännu.")
        return

    rows = []

    for match in matches:
        round_info = match.get("knockout_rounds") or {}

        kickoff_at = match.get("kickoff_at")

        rows.append(
            {
                "Match": match["match_no"],
                "Runda": round_info.get("name", "-"),
                "Avspark": (
                    format_datetime_swedish(kickoff_at)
                    if kickoff_at
                    else "-"
                ),
                "Lag 1": match["home_team"],
                "Lag 2": match["away_team"],
                "FT lag 1": match["home_goals_ft"],
                "FT lag 2": match["away_goals_ft"],
                "Status": match["status"],
            }
        )

    matches_df = pd.DataFrame(rows)

    st.dataframe(
        matches_df,
        width="stretch",
        hide_index=True,
    )

def render_knockout_match_form() -> None:
    """
    Formulär där admin kan skapa eller uppdatera en slutspelsmatch.

    match_no används som stabil nyckel.
    Om samma matchnummer sparas igen uppdateras matchen.
    """

    st.subheader("Lägg till eller uppdatera match")

    rounds = get_knockout_rounds()

    if not rounds:
        st.warning("Inga slutspelsrundor finns. Skapa rundor först.")
        return

    round_options = {
        knockout_round["id"]: knockout_round["name"]
        for knockout_round in rounds
    }

    with st.form("knockout_match_form"):
        selected_round_id = st.selectbox(
            "Runda",
            options=list(round_options.keys()),
            format_func=lambda round_id: round_options[round_id],
            key="knockout_match_round_select",
        )

        match_no = st.number_input(
            "Matchnummer",
            min_value=73,
            max_value=200,
            step=1,
            value=73,
            help=(
                "Gruppspelet använder 1–72. "
                "Slutspel kan därför börja på 73."
            ),
        )

        kickoff_date = st.date_input(
            "Avspark datum",
            value=date(2026, 6, 28),
        )

        kickoff_time = st.time_input(
            "Avspark tid svensk tid",
            value=time(18, 0),
        )

        home_team = st.text_input(
            "Lag 1",
            placeholder="Exempel: Vinnare Grupp A",
        )

        away_team = st.text_input(
            "Lag 2",
            placeholder="Exempel: Trea Grupp C/D/E",
        )

        submitted = st.form_submit_button("Spara slutspelsmatch")

    if submitted:
        cleaned_home_team = home_team.strip()
        cleaned_away_team = away_team.strip()

        if not cleaned_home_team or not cleaned_away_team:
            st.error("Båda lagen måste fyllas i.")
            return

        kickoff_iso = build_deadline_iso_from_swedish_time(
            kickoff_date,
            kickoff_time,
        )

        saved_match = upsert_knockout_match(
            {
                "round_id": selected_round_id,
                "match_no": int(match_no),
                "kickoff_at": kickoff_iso,
                "home_team": cleaned_home_team,
                "away_team": cleaned_away_team,
                "status": "scheduled",
            }
        )

        if saved_match:
            st.success(
                f"Slutspelsmatch {int(match_no)} sparad: "
                f"{cleaned_home_team} – {cleaned_away_team}"
            )
            st.info("Ladda om sidan för att se matchen i tabellen.")
        else:
            st.error("Kunde inte spara slutspelsmatchen.")

def render_knockout_csv_import_section() -> None:
    """
    Importerar slutspelsmatcher från CSV.

    CSV-format:
        match_no,round_name,kickoff_at,home_team,away_team

    Exempel:
        73,Round of 32,2026-06-28T18:00:00+02:00,Vinnare Grupp A,Trea Grupp C/D/E
    """

    st.subheader("Importera slutspelsmatcher från CSV")

    st.info(
        "CSV-filen ska innehålla kolumnerna: "
        "match_no, round_name, kickoff_at, home_team, away_team."
    )

    uploaded_file = st.file_uploader(
        "Välj CSV-fil för slutspelsmatcher",
        type=["csv"],
        key="knockout_csv_import",
    )

    if uploaded_file is None:
        return

    try:
        matches_df = pd.read_csv(uploaded_file)
    except Exception as error:
        st.error(f"Kunde inte läsa CSV-filen: {error}")
        return

    required_columns = {
        "match_no",
        "round_name",
        "kickoff_at",
        "home_team",
        "away_team",
    }

    missing_columns = required_columns - set(matches_df.columns)

    if missing_columns:
        st.error(
            "CSV-filen saknar kolumner: "
            f"{', '.join(sorted(missing_columns))}"
        )
        return

    st.write("Förhandsgranskning:")
    st.dataframe(matches_df, width="stretch", hide_index=True)

    if not st.button("Importera slutspelsmatcher"):
        return

    imported_count = 0
    errors = []

    for row_index, row in matches_df.iterrows():
        round_name = str(row["round_name"]).strip()
        knockout_round = get_knockout_round_by_name(round_name)

        if knockout_round is None:
            errors.append(
                f"Rad {row_index + 2}: okänd runda '{round_name}'"
            )
            continue

        try:
            match_no = int(row["match_no"])
        except ValueError:
            errors.append(
                f"Rad {row_index + 2}: match_no är inte ett heltal"
            )
            continue

        home_team = str(row["home_team"]).strip()
        away_team = str(row["away_team"]).strip()
        kickoff_at = str(row["kickoff_at"]).strip()

        if not home_team or not away_team:
            errors.append(
                f"Rad {row_index + 2}: home_team eller away_team saknas"
            )
            continue

        saved_match = upsert_knockout_match(
            {
                "round_id": knockout_round["id"],
                "match_no": match_no,
                "kickoff_at": kickoff_at,
                "home_team": home_team,
                "away_team": away_team,
                "status": "scheduled",
            }
        )

        if saved_match:
            imported_count += 1
        else:
            errors.append(
                f"Rad {row_index + 2}: kunde inte spara match {match_no}"
            )

    if imported_count > 0:
        st.success(f"Importerade/uppdaterade {imported_count} matcher.")

    if errors:
        st.warning("Vissa rader kunde inte importeras:")
        for error in errors:
            st.write(f"- {error}")

def render_knockout_result_admin_section() -> None:
    """
    Adminsektion för att fylla i fulltidsresultat i slutspelsmatcher.

    Viktigt:
    - Resultatet gäller efter fulltid: 90 minuter + tillägg
    - Ej förlängning
    - Ej straffläggning
    """

    st.subheader("Fyll i slutspelsresultat")

    matches = get_knockout_matches()

    if not matches:
        st.info("Inga slutspelsmatcher finns ännu.")
        return

    match_label_by_id = {}

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        round_name = round_info.get("name", "Okänd runda")

        result_text = ""

        if match["status"] == "finished":
            result_text = (
                f" ({match['home_goals_ft']}"
                f"–{match['away_goals_ft']})"
            )

        label = (
            f"Match {match['match_no']} · {round_name} – "
            f"{match['home_team']} vs {match['away_team']}"
            f"{result_text}"
        )

        match_label_by_id[match["id"]] = label

    selected_match_id = st.selectbox(
        "Välj slutspelsmatch",
        options=list(match_label_by_id.keys()),
        format_func=lambda match_id: match_label_by_id[match_id],
        key="knockout_result_match_select",
    )

    selected_match = next(
        match for match in matches
        if match["id"] == selected_match_id
    )

    st.markdown(
        f"### {selected_match['home_team']} – {selected_match['away_team']}"
    )

    st.caption(
        "Resultatet ska vara efter fulltid: 90 minuter + tillägg. "
        "Förlängning och straffar räknas inte."
    )

    current_home_goals = selected_match.get("home_goals_ft")
    current_away_goals = selected_match.get("away_goals_ft")

    home_goals_ft = st.number_input(
        f"Fulltidsmål för {selected_match['home_team']}",
        min_value=0,
        step=1,
        value=int(current_home_goals) if current_home_goals is not None else 0,
        key=f"ko_result_home_{selected_match_id}",
    )

    away_goals_ft = st.number_input(
        f"Fulltidsmål för {selected_match['away_team']}",
        min_value=0,
        step=1,
        value=int(current_away_goals) if current_away_goals is not None else 0,
        key=f"ko_result_away_{selected_match_id}",
    )

    col1, col2 = st.columns(2)

    with col1:
        save_clicked = st.button(
            "Spara slutspelsresultat",
            key="save_knockout_result",
        )

    with col2:
        clear_clicked = st.button(
            "Rensa slutspelsresultat",
            key="clear_knockout_result",
        )

    if save_clicked:
        updated_match = update_knockout_match_result(
            match_id=selected_match_id,
            home_goals_ft=int(home_goals_ft),
            away_goals_ft=int(away_goals_ft),
        )

        if updated_match:
            st.success(
                f"Resultat sparat: "
                f"{selected_match['home_team']} {int(home_goals_ft)}–"
                f"{int(away_goals_ft)} {selected_match['away_team']}"
            )
            st.info("Ladda om sidan för att se uppdaterad status i listan.")
        else:
            st.error("Kunde inte spara slutspelsresultatet.")

    if clear_clicked:
        cleared_match = clear_knockout_match_result(selected_match_id)

        if cleared_match:
            st.success("Slutspelsresultatet är rensat.")
            st.info("Ladda om sidan för att se uppdaterad status i listan.")
        else:
            st.error("Kunde inte rensa slutspelsresultatet.")

def render_knockout_admin_section() -> None:
    """
    Adminsektion för slutspelstipset.

    Första versionen:
    - visar slutspelsrundor
    - låter admin sätta deadline per runda
    - låter admin ändra status per runda
    """

    st.header("Slutspel")

    st.info(
        "Slutspelstipset är under uppbyggnad. "
        "Här börjar vi med att hantera rundor och deadlines."
    )

    rounds = get_knockout_rounds()

    if not rounds:
        st.warning("Inga slutspelsrundor finns i databasen.")
        return

    rows = []

    for knockout_round in rounds:
        deadline_at = knockout_round.get("deadline_at")

        rows.append(
            {
                "Runda": knockout_round["name"],
                "Sortering": knockout_round["sort_order"],
                "Deadline": (
                    format_datetime_swedish(deadline_at)
                    if deadline_at
                    else "-"
                ),
                "Status": knockout_round["status"],
            }
        )

    rounds_df = pd.DataFrame(rows)

    st.subheader("Rundor")

    st.dataframe(
        rounds_df,
        width="stretch",
        hide_index=True,
    )

    st.subheader("Uppdatera runda")

    round_options = {
        knockout_round["id"]: knockout_round["name"]
        for knockout_round in rounds
    }

    selected_round_id = st.selectbox(
        "Välj runda",
        options=list(round_options.keys()),
        format_func=lambda round_id: round_options[round_id],
        key="knockout_round_select",
    )

    selected_round = next(
        knockout_round
        for knockout_round in rounds
        if knockout_round["id"] == selected_round_id
    )

    status_options = [
        "not_started",
        "open",
        "locked",
        "finished",
    ]

    current_status = selected_round.get("status", "not_started")

    status_index = (
        status_options.index(current_status)
        if current_status in status_options
        else 0
    )

    with st.form("knockout_round_form"):
        selected_date = st.date_input(
            "Deadline-datum",
            value=date(2026, 6, 27),
        )

        selected_time = st.time_input(
            "Deadline-tid svensk tid",
            value=time(18, 0),
        )

        selected_status = st.selectbox(
            "Status",
            options=status_options,
            index=status_index,
        )

        submitted = st.form_submit_button("Spara runda")

    if submitted:
        deadline_iso = build_deadline_iso_from_swedish_time(
            selected_date,
            selected_time,
        )

        updated_round = update_knockout_round(
            round_id=selected_round_id,
            deadline_at=deadline_iso,
            status=selected_status,
        )

        if updated_round:
            st.success("Slutspelsrundan är uppdaterad.")
            st.info("Ladda om sidan för att se uppdaterad tabell.")
        else:
            st.error("Kunde inte uppdatera slutspelsrundan.")

    st.divider()

    st.subheader("Slutspelsmatcher")

    render_knockout_matches_table()

    render_knockout_csv_import_section()

    render_knockout_match_form()

    st.divider()

    render_knockout_result_admin_section()

    st.divider()

    render_knockout_leaderboard_section()