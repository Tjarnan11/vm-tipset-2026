# src/ui/knockout_participant.py
#
# Deltagarvy för slutspelstipset.
#
# Första versionen är read-only:
# - visar rundor
# - visar deadlines/status
# - visar matcher
#
# Senare bygger vi tipsformulär per runda.

import pandas as pd
import streamlit as st

from src.repositories.knockout_repo import (
    get_knockout_matches,
    get_knockout_rounds,
)
from src.time_utils import format_datetime_swedish


def render_knockout_rounds_overview() -> None:
    """
    Visar slutspelsrundor för deltagaren.
    """

    rounds = get_knockout_rounds()

    if not rounds:
        st.info("Slutspelet är inte förberett ännu.")
        return

    rows = []

    for knockout_round in rounds:
        deadline_at = knockout_round.get("deadline_at")

        rows.append(
            {
                "Runda": knockout_round["name"],
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


def render_knockout_matches_overview() -> None:
    """
    Visar slutspelsmatcher för deltagaren.
    """

    matches = get_knockout_matches()

    if not matches:
        st.info("Inga slutspelsmatcher är inlagda ännu.")
        return

    last_round_name = None

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        round_name = round_info.get("name", "Okänd runda")

        if round_name != last_round_name:
            st.subheader(round_name)
            last_round_name = round_name

        kickoff_at = match.get("kickoff_at")

        with st.container(border=True):
            st.markdown(
                f"**Match {match['match_no']}**"
            )

            st.markdown(
                f"### {match['home_team']} – {match['away_team']}"
            )

            if kickoff_at:
                st.caption(
                    f"Avspark: {format_datetime_swedish(kickoff_at)} svensk tid"
                )
            else:
                st.caption("Avspark: ej satt")

            if match["status"] == "finished":
                st.success(
                    f"Resultat efter fulltid: "
                    f"{match['home_team']} {match['home_goals_ft']}–"
                    f"{match['away_goals_ft']} {match['away_team']}"
                )
            else:
                st.info("Resultat: ej ifyllt ännu")


def render_knockout_participant_section() -> None:
    """
    Huvudsektion för slutspel i deltagarvyn.

    Första versionen är bara översikt.
    """

    st.header("Slutspel")

    st.info(
        "Slutspelstipset är under uppbyggnad. "
        "Här kommer du senare kunna lägga tips per slutspelsrunda."
    )

    tab_rounds, tab_matches = st.tabs(
        [
            "🏆 Rundor",
            "📅 Matcher",
        ]
    )

    with tab_rounds:
        render_knockout_rounds_overview()

    with tab_matches:
        render_knockout_matches_overview()