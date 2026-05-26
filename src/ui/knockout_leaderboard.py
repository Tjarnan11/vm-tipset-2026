# src/ui/knockout_leaderboard.py
#
# Poängtabell för slutspelstipset.

import pandas as pd
import streamlit as st

from src.knockout_scoring import build_knockout_leaderboard
from src.repositories.knockout_repo import (
    get_all_knockout_predictions,
    get_knockout_matches,
)
from src.repositories.participants_repo import get_active_participants


def render_knockout_leaderboard_section() -> None:
    """
    Visar separat slutspels-poängtabell.
    """

    st.header("Slutspelstabell")

    participants = get_active_participants()
    matches = get_knockout_matches()
    predictions = get_all_knockout_predictions()

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    finished_matches = [
        match for match in matches
        if (
            match.get("status") == "finished"
            and match.get("home_goals_ft") is not None
            and match.get("away_goals_ft") is not None
        )
    ]

    if not finished_matches:
        st.info("Inga slutspelsmatcher med resultat ännu.")
        return

    leaderboard = build_knockout_leaderboard(
        participants=participants,
        matches=matches,
        predictions=predictions,
    )

    leaderboard_df = pd.DataFrame(leaderboard)

    visible_columns = [
        "Placering",
        "Namn",
        "Poäng",
        "Exakta resultat",
        "Rätt 1X2",
        "Rätt Ö/U",
        "Rätt första målskytt",
        "Räknade matcher",
        "Maxpoäng just nu",
    ]

    leaderboard_df = leaderboard_df[visible_columns]

    st.dataframe(
        leaderboard_df,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Slutspelspoäng: 1p rätt 1/X/2, 1p rätt över/under, "
        "2p exakt resultat och 4p rätt första målskytt."
    )