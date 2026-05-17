# src/ui/results_page.py
#
# Publik vy för matcher, resultat och gruppställningar.

import pandas as pd
import streamlit as st

from src.group_tables import build_group_tables
from src.repositories.matches_repo import get_matches
from src.repositories.participants_repo import get_active_participants
from src.repositories.predictions_repo import get_all_predictions
from src.scoring import calculate_prediction_points, is_finished_match
from src.time_utils import (
    format_date_swedish,
    format_datetime_swedish,
)
from src.ui.formatting import format_goals_pick_label


def render_group_tables_section() -> None:
    """
    Visar gruppställningar baserat på inmatade resultat.

    Tabellen uppdateras automatiskt när admin fyller i matchresultat.
    """

    st.header("Grupper")

    matches = get_matches()

    if not matches:
        st.warning("Inga matcher hittades i databasen.")
        return

    group_tables = build_group_tables(matches)

    if not group_tables:
        st.info("Inga grupper hittades.")
        return

    for group_name, rows in group_tables.items():
        st.subheader(f"Grupp {group_name}")

        group_df = pd.DataFrame(rows)

        visible_columns = [
            "Lag",
            "M",
            "V",
            "O",
            "F",
            "GM",
            "IM",
            "MS",
            "P",
        ]

        group_df = group_df[visible_columns]

        st.dataframe(
            group_df,
            width="stretch",
            hide_index=True,
        )

    st.caption(
        "Tabellen sorteras efter poäng, målskillnad, gjorda mål och lagnamn. "
        "Fullständig officiell tiebreaker-logik kan läggas till senare."
    )


def render_public_matches_results_section(
    predictions_locked: bool,
) -> None:
    """
    Visar matcher, resultat och gruppställningar.

    Detta är en översiktssida för deltagaren:
    - gruppställningar
    - schema/resultat
    """

    tab_groups, tab_matches = st.tabs(
        [
            "🏆 Grupper",
            "📅 Matcher",
        ]
    )

    with tab_groups:
        render_group_tables_section()

    with tab_matches:
        st.header("Matcher & resultat")

        matches = get_matches()

        if not matches:
            st.warning("Inga matcher hittades i databasen.")
            return
        
        participants = get_active_participants() if predictions_locked else []
        predictions = get_all_predictions() if predictions_locked else []

        predictions_by_participant_and_match = {
            (prediction["participant_id"], prediction["match_id"]): prediction
            for prediction in predictions
        }

        last_date_heading = None

        for match in matches:
            date_heading = format_date_swedish(match["kickoff_at"])

            if date_heading != last_date_heading:
                st.markdown(f"### {date_heading}")
                last_date_heading = date_heading

            with st.container(border=True):
                st.markdown(
                    f"**Match {match['match_no']} · Grupp {match['group_name']}**"
                )

                st.markdown(
                    f"### {match['home_team']} – {match['away_team']}"
                )

                st.caption(
                    f"Avspark: {format_datetime_swedish(match['kickoff_at'])} svensk tid"
                )

                if is_finished_match(match):
                    st.success(
                        f"Resultat: {match['home_team']} "
                        f"{match['home_goals']}–{match['away_goals']} "
                        f"{match['away_team']}"
                    )

                    if predictions_locked:
                        rows = []

                        for participant in participants:
                            participant_id = participant["id"]

                            prediction = predictions_by_participant_and_match.get(
                                (participant_id, match["id"])
                            )

                            if prediction:
                                score = calculate_prediction_points(
                                    prediction=prediction,
                                    match=match,
                                )

                                outcome_pick = prediction["outcome_pick"]
                                goals_pick = format_goals_pick_label(
                                    prediction["goals_pick"]
                                )
                                points = score["points"]
                            else:
                                outcome_pick = "-"
                                goals_pick = "-"
                                points = 0

                            rows.append(
                                {
                                    "Namn": participant["display_name"],
                                    "1/X/2": outcome_pick,
                                    "Över/under": goals_pick,
                                    "Poäng": points,
                                }
                            )

                        points_df = pd.DataFrame(rows)

                        points_df = points_df.sort_values(
                            by=["Poäng", "Namn"],
                            ascending=[False, True],
                        )

                        with st.expander("Tips och poäng på denna match"):
                            st.dataframe(
                                points_df,
                                width="stretch",
                                hide_index=True,
                            )

                else:
                    st.info("Resultat: ej ifyllt ännu")

                    if predictions_locked:
                        rows = []

                        for participant in participants:
                            participant_id = participant["id"]

                            prediction = predictions_by_participant_and_match.get(
                                (participant_id, match["id"])
                            )

                            if prediction:
                                outcome_pick = prediction["outcome_pick"]
                                goals_pick = format_goals_pick_label(
                                    prediction["goals_pick"]
                                )
                            else:
                                outcome_pick = "-"
                                goals_pick = "-"

                            rows.append(
                                {
                                    "Namn": participant["display_name"],
                                    "1/X/2": outcome_pick,
                                    "Över/under": goals_pick,
                                }
                            )

                        tips_df = pd.DataFrame(rows)

                        with st.expander("Tips på denna match"):
                            st.dataframe(
                                tips_df,
                                width="stretch",
                                hide_index=True,
                            )
