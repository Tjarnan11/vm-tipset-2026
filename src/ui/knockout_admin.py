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
    get_knockout_rounds,
    update_knockout_round,
)
from src.time_utils import format_datetime_swedish


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