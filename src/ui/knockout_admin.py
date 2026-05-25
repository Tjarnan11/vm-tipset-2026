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
    get_knockout_matches,
    get_knockout_rounds,
    update_knockout_round,
    upsert_knockout_match,
)

from src.time_utils import format_datetime_swedish

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

    render_knockout_match_form()