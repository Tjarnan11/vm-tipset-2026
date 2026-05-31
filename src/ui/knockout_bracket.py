# src/ui/knockout_bracket.py
#
# Enkel bracket-/slutspelsträd-vy.
#
# Första versionen visar matcher grupperade per runda i kolumner.
# Den försöker inte rita kopplingslinjer mellan matcher.

import streamlit as st

from src.repositories.knockout_repo import get_knockout_matches
from src.time_utils import format_datetime_swedish


def is_finished_knockout_match(match: dict) -> bool:
    """
    Kontrollerar om en slutspelsmatch har fulltidsresultat.
    """

    return (
        match.get("status") == "finished"
        and match.get("home_goals_ft") is not None
        and match.get("away_goals_ft") is not None
    )


def format_knockout_bracket_match_title(match: dict) -> str:
    """
    Returnerar matchtext för bracket-kort.

    Om resultat finns:
        Argentina 2–1 Frankrike

    Annars:
        Argentina – Frankrike
    """

    if is_finished_knockout_match(match):
        return (
            f"{match['home_team']} {match['home_goals_ft']}–"
            f"{match['away_goals_ft']} {match['away_team']}"
        )

    return f"{match['home_team']} – {match['away_team']}"


def render_knockout_bracket_section() -> None:
    """
    Visar en enkel slutspelsträd-vy.

    Matcherna grupperas efter runda och visas i kolumner.
    """

    st.header("Slutspelsträd")

    st.caption(
        "Första versionen visar slutspelsmatcherna runda för runda. "
        "Ett mer grafiskt bracket med linjer kan läggas till senare."
    )

    matches = get_knockout_matches()

    if not matches:
        st.info("Inga slutspelsmatcher är inlagda ännu.")
        return

    matches_by_round_name = {}

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        round_name = round_info.get("name", "Okänd runda")
        sort_order = round_info.get("sort_order", 999)

        if round_name not in matches_by_round_name:
            matches_by_round_name[round_name] = {
                "sort_order": sort_order,
                "matches": [],
            }

        matches_by_round_name[round_name]["matches"].append(match)

    ordered_rounds = sorted(
        matches_by_round_name.items(),
        key=lambda item: item[1]["sort_order"],
    )

    columns = st.columns(len(ordered_rounds))

    for column, (round_name, round_data) in zip(columns, ordered_rounds):
        with column:
            st.subheader(round_name)

            round_matches = sorted(
                round_data["matches"],
                key=lambda match: match["match_no"],
            )

            for match in round_matches:
                kickoff_at = match.get("kickoff_at")

                with st.container(border=True):
                    st.caption(f"Match {match['match_no']}")

                    st.markdown(
                        f"**{format_knockout_bracket_match_title(match)}**"
                    )

                    if kickoff_at:
                        st.caption(
                            f"{format_datetime_swedish(kickoff_at)}"
                        )

                    if is_finished_knockout_match(match):
                        st.success("FT-resultat")
                    else:
                        st.caption("Ej spelad")