# src/ui/leaderboard_page.py
#
# Poängtabell och publik översikt över allas tips efter deadline.

import pandas as pd
import streamlit as st

from src.repositories.bonus_repo import (
    get_all_bonus_predictions,
    get_bonus_scorer_results,
)
from src.repositories.matches_repo import get_matches
from src.repositories.participants_repo import get_active_participants
from src.repositories.predictions_repo import get_all_predictions
from src.scoring import (
    build_leaderboard,
    calculate_prediction_points,
    get_goals_pick,
    get_match_outcome,
    is_finished_match,
)
from src.time_utils import format_datetime_swedish
from src.ui.formatting import format_goals_pick_label


def render_leaderboard_section() -> None:
    """
    Visar poängtabellen.

    Poängen räknas dynamiskt från:
    - deltagare
    - matcher med resultat
    - sparade tips

    Vi sparar alltså inte totalpoäng i databasen.
    Det minskar risken för att poängtabellen blir fel eller inaktuell.
    """

    st.header("Gruppspel – Poängtabell")

    participants = get_active_participants()
    matches = get_matches()
    predictions = get_all_predictions()
    bonus_predictions = get_all_bonus_predictions()
    bonus_results = get_bonus_scorer_results()

    finished_matches = [
        match for match in matches
        if (
            match.get("status") == "finished"
            and match.get("home_goals") is not None
            and match.get("away_goals") is not None
        )
    ]

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    if not finished_matches:
        st.info("Inga färdigspelade matcher med resultat ännu.")
        return

    leaderboard = build_leaderboard(
        participants=participants,
        matches=matches,
        predictions=predictions,
        bonus_predictions=bonus_predictions,
        bonus_results=bonus_results,
    )

    leaderboard_df = pd.DataFrame(leaderboard)

    visible_columns = [
        "Placering",
        "Namn",
        "Poäng",
        "Bonusspelare",
        "Bonusmål",
        "Rätt 1X2",
        "Rätt Ö/U",
        "Räknade matcher",
    ]

    leaderboard_df = leaderboard_df[visible_columns]

    st.dataframe(
        leaderboard_df,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Poäng: 1 poäng för rätt 1/X/2 och 1 poäng för rätt över/under 2,5 mål."
    )


def render_public_predictions_overview_section() -> None:
    """
    Visar allas tips efter deadline.

    Deltagaren kan välja en match och se:
    - varje deltagares 1/X/2-tips
    - varje deltagares över/under-tips
    - poäng på matchen om resultat finns

    Den här funktionen ska bara visas efter deadline.
    """

    st.header("Allas gruppspelstips")

    participants = get_active_participants()
    matches = get_matches()
    predictions = get_all_predictions()

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    if not matches:
        st.warning("Inga matcher hittades.")
        return

    predictions_by_participant_and_match = {
        (prediction["participant_id"], prediction["match_id"]): prediction
        for prediction in predictions
    }

    match_label_by_id = {}

    for match in matches:
        result_text = ""

        if is_finished_match(match):
            result_text = f" ({match['home_goals']}–{match['away_goals']})"

        label = (
            f"Match {match['match_no']} – "
            f"{format_datetime_swedish(match['kickoff_at'])} – "
            f"{match['home_team']} vs {match['away_team']}"
            f"{result_text}"
        )

        match_label_by_id[match["id"]] = label

    selected_match_id = st.selectbox(
        "Välj match",
        options=list(match_label_by_id.keys()),
        format_func=lambda match_id: match_label_by_id[match_id],
        key="public_predictions_match_select",
    )

    selected_match = next(
        match for match in matches
        if match["id"] == selected_match_id
    )

    st.caption(
        f"Match {selected_match['match_no']} · Grupp {selected_match['group_name']} · "
        f"{format_datetime_swedish(selected_match['kickoff_at'])}"
    )

    st.markdown(
        f"### {selected_match['home_team']} – {selected_match['away_team']}"
    )

    selected_match_is_finished = is_finished_match(selected_match)

    if selected_match_is_finished:
        home_goals = int(selected_match["home_goals"])
        away_goals = int(selected_match["away_goals"])

        correct_outcome = get_match_outcome(home_goals, away_goals)
        correct_goals_pick = get_goals_pick(home_goals, away_goals)

        st.success(
            f"Resultat: {selected_match['home_team']} "
            f"{home_goals}–{away_goals} "
            f"{selected_match['away_team']}"
        )

        st.caption(
            f"Rätt rad: {correct_outcome} · "
            f"{format_goals_pick_label(correct_goals_pick)}"
        )
    else:
        st.info("Resultat är inte ifyllt ännu.")

    rows = []

    for participant in participants:
        participant_id = participant["id"]

        prediction = predictions_by_participant_and_match.get(
            (participant_id, selected_match_id)
        )

        if prediction:
            outcome_pick = prediction["outcome_pick"]
            goals_pick = format_goals_pick_label(prediction["goals_pick"])

            if selected_match_is_finished:
                score = calculate_prediction_points(
                    prediction=prediction,
                    match=selected_match,
                )

                points = str(score["points"])
            else:
                points = "-"
        else:
            outcome_pick = "-"
            goals_pick = "-"

            if selected_match_is_finished:
                points = "0"
            else:
                points = "-"

        # Viktigt:
        # rows.append ska ligga UTANFÖR if/else ovan.
        # Annars råkar vi bara visa deltagare som saknar tips.
        rows.append(
            {
                "Namn": participant["display_name"],
                "1/X/2": outcome_pick,
                "Över/under": goals_pick,
                "Poäng": points,
            }
        )

    predictions_df = pd.DataFrame(rows)

    st.dataframe(
        predictions_df,
        width="stretch",
        hide_index=True,
    )

