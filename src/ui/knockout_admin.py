# src/ui/knockout_admin.py
#
# Admin-UI för slutspelstipset.
#
# Första versionen visar bara rundor och låter admin uppdatera
# deadline/status. Matchinmatning kommer i nästa pass.

from datetime import date, time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import re

from src.deadline import (
    build_deadline_iso_from_swedish_time,
    is_deadline_passed,
)

from src.repositories.knockout_repo import (
    clear_knockout_match_result,
    get_all_knockout_predictions,
    get_all_knockout_final_predictions,
    get_knockout_matches,
    get_knockout_round_by_name,
    get_knockout_rounds,        
    update_first_scorer_correct,
    update_knockout_match_result,
    update_knockout_match_teams,
    update_knockout_round,
    upsert_knockout_match,
    update_knockout_match_first_scorer,
)

from src.time_utils import format_datetime_swedish

from src.ui.knockout_leaderboard import render_knockout_leaderboard_section

from src.repositories.participants_repo import get_active_participants

from src.ui.knockout_final import (
    render_knockout_final_admin_section,
    render_knockout_final_review_admin_section,
)

from src.repositories.matches_repo import get_matches


def _format_admin_updated_at(value) -> str:
    if not value:
        return "-"

    try:
        if isinstance(value, str):
            datetime_value = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        elif isinstance(value, datetime):
            datetime_value = value
        else:
            return str(value)

        if datetime_value.tzinfo is None:
            datetime_value = datetime_value.replace(tzinfo=ZoneInfo("UTC"))

        swedish_time = datetime_value.astimezone(
            ZoneInfo("Europe/Stockholm")
        )

        month_names = {
            1: "januari",
            2: "februari",
            3: "mars",
            4: "april",
            5: "maj",
            6: "juni",
            7: "juli",
            8: "augusti",
            9: "september",
            10: "oktober",
            11: "november",
            12: "december",
        }

        month_name = month_names[swedish_time.month]

        return (
            f"{swedish_time.day} {month_name} {swedish_time.year}, "
            f"{swedish_time:%H:%M}"
        )

    except ValueError:
        return str(value)

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
                "Struktur lag 1": match.get("home_placeholder") or "",
                "Struktur lag 2": match.get("away_placeholder") or "",
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
                "home_placeholder": cleaned_home_team,
                "away_placeholder": cleaned_away_team,
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

    home_placeholder = (
        selected_match.get("home_placeholder")
        or selected_match.get("home_team")
        or "-"
    )

    away_placeholder = (
        selected_match.get("away_placeholder")
        or selected_match.get("away_team")
        or "-"
    )

    st.info(
        "Originalstruktur: "
        f"{home_placeholder} – {away_placeholder}"
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

    current_first_scorer = selected_match.get("first_scorer") or ""

    first_scorer = st.text_input(
        "Faktisk första målskytt",
        value=current_first_scorer,
        placeholder="Exempel: Kylian Mbappé",
        help=(
            "Gäller första målskytt under ordinarie tid. "
            "Används för visning; poängen sätts via målskyttsbedömningen."
        ),
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

        update_knockout_match_first_scorer(
            match_id=selected_match_id,
            first_scorer=first_scorer,
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
        update_knockout_match_first_scorer(
            match_id=selected_match_id,
            first_scorer=None,
        )

        if cleared_match:
            st.success("Slutspelsresultatet är rensat.")
            st.info("Ladda om sidan för att se uppdaterad status i listan.")
        else:
            st.error("Kunde inte rensa slutspelsresultatet.")

def format_first_scorer_status(value: bool | None) -> str:
    """
    Gör om first_scorer_correct till läsbar admintext.
    """

    if value is True:
        return "Rätt"

    if value is False:
        return "Fel"

    return "Ej bedömt"


def parse_first_scorer_status(label: str) -> bool | None:
    """
    Gör om adminvalet till databasvärde.
    """

    if label == "Rätt":
        return True

    if label == "Fel":
        return False

    return None

def is_knockout_round_public(knockout_round: dict) -> bool:
    """
    Kontrollerar om en slutspelsrundas tips får visas.

    Tips får visas först när:
    - rundans deadline har passerat
    - eller rundan är locked/finished
    """

    status = knockout_round.get("status", "not_started")
    deadline_at = knockout_round.get("deadline_at")

    deadline_passed = (
        is_deadline_passed(deadline_at)
        if deadline_at
        else False
    )

    return status in {"locked", "finished"} or deadline_passed

def render_first_scorer_admin_section() -> None:
    """
    Adminsektion för att bedöma första målskytt i slutspelsmatcher.

    Deltagarna skriver målskytt som fritext.
    Admin markerar varje deltagares tips som:
    - Ej bedömt
    - Rätt
    - Fel

    Viktigt:
    Tipsen visas först när matchens runda är publik.
    """

    st.subheader("Bedöm första målskytt")

    matches = get_knockout_matches()
    participants = get_active_participants()

    if not matches:
        st.info("Inga slutspelsmatcher finns ännu.")
        return

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    participant_name_by_id = {
        participant["id"]: participant["display_name"]
        for participant in participants
    }

    match_label_by_id = {}

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        round_name = round_info.get("name", "Okänd runda")

        label = (
            f"Match {match['match_no']} · {round_name} – "
            f"{match['home_team']} vs {match['away_team']}"
        )

        match_label_by_id[match["id"]] = label

    selected_match_id = st.selectbox(
        "Välj match för målskytt-bedömning",
        options=list(match_label_by_id.keys()),
        format_func=lambda match_id: match_label_by_id[match_id],
        key="first_scorer_match_select",
    )

    selected_match = next(
        match for match in matches
        if match["id"] == selected_match_id
    )

    selected_round = selected_match.get("knockout_rounds") or {}

    if not is_knockout_round_public(selected_round):
        st.info(
            "Första målskytt-tips för den här rundan visas först när rundans "
            "deadline har passerat eller när rundan är låst."
        )
        return

    predictions = get_all_knockout_predictions()

    if not predictions:
        st.info("Inga slutspelstips finns ännu.")
        return

    actual_first_scorer = selected_match.get("first_scorer")

    if actual_first_scorer:
        st.info(f"Faktisk första målskytt: {actual_first_scorer}")
    else:
        st.warning(
            "Ingen faktisk första målskytt är sparad för denna match ännu. "
            "Fyll i den under Resultat-fliken."
        )

    st.markdown(
        f"### {selected_match['home_team']} – {selected_match['away_team']}"
    )

    predictions_for_match = [
        prediction for prediction in predictions
        if prediction["match_id"] == selected_match_id
    ]

    if not predictions_for_match:
        st.info("Ingen deltagare har tippat denna match ännu.")
        return

    status_options = [
        "Ej bedömt",
        "Rätt",
        "Fel",
    ]

    rows = []

    for prediction in predictions_for_match:
        rows.append(
            {
                "Deltagare": participant_name_by_id.get(
                    prediction["participant_id"],
                    "Okänd deltagare",
                ),
                "Första målskytt": prediction.get("first_scorer_pick") or "-",
                "Status": format_first_scorer_status(
                    prediction.get("first_scorer_correct")
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Tips markerade som Rätt ger 4 poäng i slutspelstabellen. "
        "Ej bedömt och Fel ger 0 poäng."
    )

    st.subheader("Uppdatera bedömning")

    prediction_label_by_id = {}

    for prediction in predictions_for_match:
        participant_name = participant_name_by_id.get(
            prediction["participant_id"],
            "Okänd deltagare",
        )

        first_scorer_pick = prediction.get("first_scorer_pick") or "-"

        prediction_label_by_id[prediction["id"]] = (
            f"{participant_name}: {first_scorer_pick}"
        )

    selected_prediction_id = st.selectbox(
        "Välj deltagarens målskytt-tips",
        options=list(prediction_label_by_id.keys()),
        format_func=lambda prediction_id: prediction_label_by_id[prediction_id],
        key="first_scorer_prediction_select",
    )

    selected_prediction = next(
        prediction for prediction in predictions_for_match
        if prediction["id"] == selected_prediction_id
    )

    current_status_label = format_first_scorer_status(
        selected_prediction.get("first_scorer_correct")
    )

    current_status_index = status_options.index(current_status_label)

    selected_status_label = st.selectbox(
        "Bedömning",
        options=status_options,
        index=current_status_index,
        key="first_scorer_status_select",
    )

    if st.button("Spara målskytt-bedömning"):
        saved_value = parse_first_scorer_status(selected_status_label)

        updated_prediction = update_first_scorer_correct(
            prediction_id=selected_prediction_id,
            first_scorer_correct=saved_value,
        )

        if updated_prediction:
            st.success("Målskytt-bedömningen är sparad.")
            st.info("Ladda om sidan för att se uppdaterad tabell.")
        else:
            st.error("Kunde inte spara målskytt-bedömningen.")


def _get_all_group_stage_teams() -> list[str]:
    matches = get_matches()

    teams = set()

    for match in matches:
        home_team = match.get("home_team")
        away_team = match.get("away_team")

        if home_team:
            teams.add(home_team)

        if away_team:
            teams.add(away_team)

    return sorted(teams)


def _get_teams_by_group() -> dict[str, list[str]]:
    matches = get_matches()

    teams_by_group: dict[str, set[str]] = {}

    for match in matches:
        group_name = match.get("group_name")

        if not group_name:
            continue

        group_name = str(group_name).upper()

        teams_by_group.setdefault(group_name, set())

        home_team = match.get("home_team")
        away_team = match.get("away_team")

        if home_team:
            teams_by_group[group_name].add(home_team)

        if away_team:
            teams_by_group[group_name].add(away_team)

    return {
        group_name: sorted(teams)
        for group_name, teams in teams_by_group.items()
    }


def _extract_group_letters_from_placeholder(placeholder: str | None) -> list[str]:
    if not placeholder:
        return []

    text = str(placeholder).upper()

    # Fångar både:
    # - "Grupp A"
    # - "Grupp A/C/D/E"
    # - "A/C/D/E"
    #
    # Begränsat till gruppbokstäver A-L.
    group_letters = re.findall(r"\b[A-L]\b", text)

    return sorted(set(group_letters))


def _get_candidate_teams_for_placeholder(
    placeholder: str | None,
    teams_by_group: dict[str, list[str]],
    all_teams: list[str],
) -> tuple[list[str], str]:
    group_letters = _extract_group_letters_from_placeholder(placeholder)

    if not group_letters:
        return all_teams, "Visar alla lag eftersom platsen inte kunde kopplas till en specifik grupp."

    candidate_teams = []

    for group_letter in group_letters:
        candidate_teams.extend(teams_by_group.get(group_letter, []))

    candidate_teams = sorted(set(candidate_teams))

    if not candidate_teams:
        return all_teams, "Visar alla lag eftersom gruppkandidater saknas."

    if len(group_letters) == 1:
        help_text = f"Förslag från grupp {group_letters[0]}."

    else:
        groups_text = ", ".join(group_letters)
        help_text = f"Förslag från grupperna {groups_text}."

    return candidate_teams, help_text


def _build_team_select_options(
    candidate_teams: list[str],
    current_team: str | None,
) -> list[str]:
    options = [""]

    for team in candidate_teams:
        if team not in options:
            options.append(team)

    if current_team and current_team not in options:
        options.append(current_team)

    return options

def render_knockout_team_update_form() -> None:
    """
    Formulär där admin kan ersätta placeholders med faktiska lag.

    Detta ändrar bara:
    - home_team
    - away_team

    Det ändrar inte:
    - matchnummer
    - runda
    - avspark
    - resultat
    """

    st.subheader("Uppdatera lag i slutspelsmatch")

    matches = get_knockout_matches()

    if not matches:
        st.info("Inga slutspelsmatcher finns ännu.")
        return

    all_teams = _get_all_group_stage_teams()
    teams_by_group = _get_teams_by_group()

    match_label_by_id = {}

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        round_name = round_info.get("name", "Okänd runda")

        home_placeholder = match.get("home_placeholder") or match.get("home_team")
        away_placeholder = match.get("away_placeholder") or match.get("away_team")

        match_label_by_id[match["id"]] = (
            f"Match {match['match_no']} · {round_name} – "
            f"{home_placeholder} vs {away_placeholder}"
        )

    selected_match_id = st.selectbox(
        "Välj match",
        options=list(match_label_by_id.keys()),
        format_func=lambda match_id: match_label_by_id[match_id],
        key="knockout_team_update_match_select",
    )

    selected_match = next(
        match for match in matches
        if match["id"] == selected_match_id
    )

    current_home_team = selected_match.get("home_team") or ""
    current_away_team = selected_match.get("away_team") or ""

    home_placeholder = selected_match.get("home_placeholder") or current_home_team
    away_placeholder = selected_match.get("away_placeholder") or current_away_team

    home_candidates, home_help_text = _get_candidate_teams_for_placeholder(
        home_placeholder,
        teams_by_group,
        all_teams,
    )

    away_candidates, away_help_text = _get_candidate_teams_for_placeholder(
        away_placeholder,
        teams_by_group,
        all_teams,
    )

    home_options = _build_team_select_options(
        home_candidates,
        current_home_team,
    )

    away_options = _build_team_select_options(
        away_candidates,
        current_away_team,
    )

    home_index = (
        home_options.index(current_home_team)
        if current_home_team in home_options
        else 0
    )

    away_index = (
        away_options.index(current_away_team)
        if current_away_team in away_options
        else 0
    )

    st.caption(
        f"Originalplatser: **{home_placeholder}** – **{away_placeholder}**"
    )

    with st.form("knockout_team_update_form"):
        col_home, col_away = st.columns(2)

        with col_home:
            selected_home_team = st.selectbox(
                "Lag 1",
                options=home_options,
                index=home_index,
                format_func=lambda value: value if value else "Välj lag",
                help=home_help_text,
                key=f"knockout_home_team_{selected_match_id}",
            )

        with col_away:
            selected_away_team = st.selectbox(
                "Lag 2",
                options=away_options,
                index=away_index,
                format_func=lambda value: value if value else "Välj lag",
                help=away_help_text,
                key=f"knockout_away_team_{selected_match_id}",
            )

        col_save, col_reset = st.columns(2)

        with col_save:
            submitted = st.form_submit_button("Spara lag")

        with col_reset:
            reset_submitted = st.form_submit_button("Återställ till originalplatser")

    if reset_submitted:
        if not home_placeholder or not away_placeholder:
            st.error("Originalplatser saknas för den här matchen.")
            return

        updated_match = update_knockout_match_teams(
            match_id=selected_match_id,
            home_team=home_placeholder,
            away_team=away_placeholder,
        )

        if updated_match:
            st.success(
                f"Match {selected_match['match_no']} återställd till: "
                f"{home_placeholder} – {away_placeholder}"
            )
            st.info("Ladda om sidan för att se uppdateringen i tabellen.")
        else:
            st.error("Kunde inte återställa lagen.")

        return

    if submitted:
        cleaned_home_team = selected_home_team.strip()
        cleaned_away_team = selected_away_team.strip()

        if not cleaned_home_team or not cleaned_away_team:
            st.error("Båda lagen måste väljas.")
            return

        updated_match = update_knockout_match_teams(
            match_id=selected_match_id,
            home_team=cleaned_home_team,
            away_team=cleaned_away_team,
        )

        if updated_match:
            st.success(
                f"Match {selected_match['match_no']} uppdaterad: "
                f"{cleaned_home_team} – {cleaned_away_team}"
            )
            st.info("Ladda om sidan för att se uppdateringen i tabellen.")
        else:
            st.error("Kunde inte uppdatera lagen.")

def _build_knockout_round_status_rows(
    participants: list[dict],
    knockout_round: dict,
    matches: list[dict],
    predictions: list[dict],
) -> list[dict]:
    round_id = knockout_round["id"]

    round_matches = []

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        match_round_id = match.get("round_id") or round_info.get("id")

        if match_round_id == round_id:
            round_matches.append(match)

    round_match_ids = {
        match["id"]
        for match in round_matches
    }

    total_matches = len(round_matches)

    predictions_by_participant_id: dict[str, list[dict]] = {}

    for prediction in predictions:
        participant_id = prediction.get("participant_id")
        match_id = prediction.get("match_id")

        if not participant_id or match_id not in round_match_ids:
            continue

        predictions_by_participant_id.setdefault(
            participant_id,
            [],
        ).append(prediction)

    rows = []

    for participant in participants:
        participant_id = participant["id"]
        participant_predictions = predictions_by_participant_id.get(
            participant_id,
            [],
        )

        prediction_count = len(participant_predictions)

        first_scorer_count = sum(
            1
            for prediction in participant_predictions
            if _has_value(prediction.get("first_scorer_pick"))
        )

        latest_updated_at = None

        for prediction in participant_predictions:
            updated_at = prediction.get("updated_at")

            if updated_at and (
                latest_updated_at is None or updated_at > latest_updated_at
            ):
                latest_updated_at = updated_at

        rows.append(
            {
                "Deltagare": _get_participant_name(participant),
                "Matchtips": f"{prediction_count}/{total_matches}",
                "Första målskytt": (
                    f"{first_scorer_count}/{prediction_count}"
                    if prediction_count
                    else "0/0"
                ),
                "Senast uppdaterad": _format_admin_updated_at(latest_updated_at),
                "_prediction_count": prediction_count,
                "_first_scorer_count": first_scorer_count,
            }
        )

    return rows


def _build_knockout_final_status_rows(
    participants: list[dict],
    final_predictions: list[dict],
) -> list[dict]:
    final_prediction_by_participant_id = {
        prediction.get("participant_id"): prediction
        for prediction in final_predictions
        if prediction.get("participant_id")
    }

    rows = []

    for participant in participants:
        participant_id = participant["id"]
        final_prediction = final_prediction_by_participant_id.get(participant_id)

        if not final_prediction:
            status = "Saknas"
            updated_at = "-"
            status_order = 0

        else:
            has_complete_final_prediction = (
                _has_value(final_prediction.get("finalist_1"))
                and _has_value(final_prediction.get("finalist_2"))
                and _has_value(final_prediction.get("winner"))
            )

            status = "Sparat" if has_complete_final_prediction else "Påbörjat"
            updated_at = _format_admin_updated_at(
                final_prediction.get("updated_at")
            )
            status_order = 2 if has_complete_final_prediction else 1

        rows.append(
            {
                "Deltagare": _get_participant_name(participant),
                "Finaltips": status,
                "Senast uppdaterad": updated_at,
                "_status_order": status_order,
            }
        )

    return rows

def _has_value(value) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _get_participant_name(participant: dict) -> str:
    return (
        participant.get("display_name")
        or participant.get("name")
        or "Okänd deltagare"
    )


def _build_knockout_status_rows(
    participants: list[dict],
    rounds: list[dict],
    matches: list[dict],
    predictions: list[dict],
    final_predictions: list[dict],
) -> list[dict]:
    matches_by_round_id: dict[str, list[dict]] = {}

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        round_id = match.get("round_id") or round_info.get("id")

        if not round_id:
            continue

        matches_by_round_id.setdefault(round_id, []).append(match)

    match_by_id = {
        match["id"]: match
        for match in matches
    }

    predictions_by_participant_and_round: dict[tuple[str, str], list[dict]] = {}

    for prediction in predictions:
        participant_id = prediction.get("participant_id")
        match_id = prediction.get("match_id")
        match = match_by_id.get(match_id)

        if not participant_id or not match:
            continue

        round_info = match.get("knockout_rounds") or {}
        round_id = match.get("round_id") or round_info.get("id")

        if not round_id:
            continue

        key = (participant_id, round_id)
        predictions_by_participant_and_round.setdefault(key, []).append(prediction)

    final_prediction_by_participant_id = {
        prediction.get("participant_id"): prediction
        for prediction in final_predictions
        if prediction.get("participant_id")
    }

    sorted_rounds = sorted(
        rounds,
        key=lambda knockout_round: knockout_round.get("sort_order", 999),
    )

    rows = []

    for participant in participants:
        participant_id = participant["id"]

        row = {
            "Deltagare": _get_participant_name(participant),
        }

        latest_updated_at = None

        for knockout_round in sorted_rounds:
            round_id = knockout_round["id"]
            round_name = knockout_round.get("name", "Okänd runda")

            round_matches = matches_by_round_id.get(round_id, [])
            total_matches = len(round_matches)

            round_predictions = predictions_by_participant_and_round.get(
                (participant_id, round_id),
                [],
            )

            prediction_count = len(round_predictions)

            first_scorer_count = sum(
                1
                for prediction in round_predictions
                if _has_value(prediction.get("first_scorer_pick"))
            )

            row[round_name] = f"{prediction_count}/{total_matches}"

            row[f"{round_name} målskytt"] = (
                f"{first_scorer_count}/{prediction_count}"
                if prediction_count
                else "0/0"
            )

            for prediction in round_predictions:
                updated_at = prediction.get("updated_at")

                if updated_at and (
                    latest_updated_at is None or updated_at > latest_updated_at
                ):
                    latest_updated_at = updated_at

        final_prediction = final_prediction_by_participant_id.get(participant_id)

        if final_prediction:
            has_complete_final_prediction = (
                _has_value(final_prediction.get("finalist_1"))
                and _has_value(final_prediction.get("finalist_2"))
                and _has_value(final_prediction.get("winner"))
            )

            row["Finaltips"] = "Sparat" if has_complete_final_prediction else "Påbörjat"

            updated_at = final_prediction.get("updated_at")

            if updated_at and (
                latest_updated_at is None or updated_at > latest_updated_at
            ):
                latest_updated_at = updated_at
        else:
            row["Finaltips"] = "Saknas"

        row["Senast uppdaterad"] = latest_updated_at or "-"

        rows.append(row)

    return rows

def render_knockout_participant_status_admin_section() -> None:
    """
    Visar adminstatus för slutspelstips utan att avslöja tipsens innehåll.
    """

    st.subheader("Slutspel – deltagarstatus")

    st.caption(
        "Här visas bara hur många tips som är sparade per deltagare och runda. "
        "Själva tipsen visas inte före respektive rundas deadline eller låsning."
    )

    participants = get_active_participants()
    rounds = get_knockout_rounds()
    matches = get_knockout_matches()
    predictions = get_all_knockout_predictions()
    final_predictions = get_all_knockout_final_predictions()

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    if not rounds:
        st.info("Inga slutspelsrundor finns ännu.")
        return

    sorted_rounds = sorted(
        rounds,
        key=lambda knockout_round: knockout_round.get("sort_order", 999),
    )

    round_label_by_id = {
        knockout_round["id"]: knockout_round.get("name", "Okänd runda")
        for knockout_round in sorted_rounds
    }

    selected_round_id = st.selectbox(
        "Välj runda",
        options=list(round_label_by_id.keys()),
        format_func=lambda round_id: round_label_by_id[round_id],
        key="knockout_participant_status_round_select",
    )

    selected_round = next(
        knockout_round for knockout_round in sorted_rounds
        if knockout_round["id"] == selected_round_id
    )

    round_rows = _build_knockout_round_status_rows(
        participants=participants,
        knockout_round=selected_round,
        matches=matches,
        predictions=predictions,
    )

    round_df = pd.DataFrame(round_rows)

    if round_df.empty:
        st.info("Ingen status att visa för vald runda.")
    else:
        total_participants = len(round_df)
        completed_participants = int(
            (
                round_df["_prediction_count"]
                == round_df["Matchtips"].str.split("/").str[1].astype(int)
            ).sum()
        )
        started_participants = int((round_df["_prediction_count"] > 0).sum())

        total_saved_predictions = int(round_df["_prediction_count"].sum())
        total_first_scorers = int(round_df["_first_scorer_count"].sum())

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Har påbörjat rundan",
            f"{started_participants}/{total_participants}",
        )

        col2.metric(
            "Har fyllt hela rundan",
            f"{completed_participants}/{total_participants}",
        )

        col3.metric(
            "Första målskytt ifyllt",
            f"{total_first_scorers}/{total_saved_predictions}",
        )

        display_round_df = (
            round_df.sort_values(
                ["_prediction_count", "_first_scorer_count", "Deltagare"],
                ascending=[True, True, True],
            )
            .drop(
                columns=[
                    "_prediction_count",
                    "_first_scorer_count",
                ]
            )
        )

        st.dataframe(
            display_round_df,
            width="stretch",
            hide_index=True,
        )

    st.divider()

    st.subheader("Finaltips-status")

    final_rows = _build_knockout_final_status_rows(
        participants=participants,
        final_predictions=final_predictions,
    )

    final_df = pd.DataFrame(final_rows)

    if final_df.empty:
        st.info("Ingen finaltips-status att visa.")
        return

    display_final_df = (
        final_df.sort_values(
            ["_status_order", "Deltagare"],
            ascending=[True, True],
        )
        .drop(columns=["_status_order"])
    )

    st.dataframe(
        display_final_df,
        width="stretch",
        hide_index=True,
    )

def render_knockout_rounds_admin_section() -> None:
    """
    Adminsektion för slutspelsrundor.

    Visar slutspelsrundor och låter admin uppdatera deadline/status.
    """

    st.subheader("Slutspelsrundor")

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



def render_knockout_admin_section() -> None:
    """
    Adminsektion för slutspelstipset.

    Slutspelsadmin är uppdelad i interna flikar för att undvika
    en lång sida med många rubriker.
    """

    st.header("Slutspel")

    st.info(
        "Här hanteras slutspelstipset: rundor, matcher, resultat, "
        "målskyttsbedömning, finaltips och slutspelstabell."
    )

    (
        tab_overview,
        tab_rounds,
        tab_matches,
        tab_results,
        tab_first_scorer,
        tab_final,
        tab_leaderboard,
    ) = st.tabs(
        [
            "🏠 Översikt",
            "⏰ Rundor",
            "📅 Matcher",
            "✍️ Resultat",
            "⚽ Målskytt",
            "🏁 Final",
            "📊 Tabell",
        ]
    )

    with tab_overview:
        st.subheader("Slutspelsöversikt")

        rounds = get_knockout_rounds()
        matches = get_knockout_matches()

        st.metric("Slutspelsrundor", len(rounds))
        st.metric("Slutspelsmatcher", len(matches))

        st.caption(
            "Tips öppnas per runda. En runda är tippbar när status är "
            "`open` och deadline ligger i framtiden."
        )

        render_knockout_participant_status_admin_section()

    with tab_rounds:
        render_knockout_rounds_admin_section()

    with tab_matches:
        render_knockout_matches_table()

        st.divider()

        render_knockout_csv_import_section()

        st.divider()

        render_knockout_team_update_form()

    with tab_results:
        render_knockout_result_admin_section()

    with tab_first_scorer:
        render_first_scorer_admin_section()

    with tab_final:
        render_knockout_final_admin_section()

        st.divider()

        render_knockout_final_review_admin_section()

    with tab_leaderboard:
        render_knockout_leaderboard_section()