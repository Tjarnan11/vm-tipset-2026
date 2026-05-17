# src/knockout_scoring.py
#
# Poänglogik för slutspelstipset.
#
# Den här filen byggs ut senare.
# Just nu lägger vi grunden för härledd 1/X/2 och över/under.

from src.scoring import get_goals_pick, get_match_outcome


def get_knockout_prediction_outcome(
    predicted_home_goals: int,
    predicted_away_goals: int,
) -> str:
    """
    Härleder 1/X/2 från deltagarens exakta resultat.
    """

    return get_match_outcome(
        predicted_home_goals,
        predicted_away_goals,
    )


def is_finished_knockout_match(match: dict) -> bool:
    """
    Kontrollerar om en slutspelsmatch har fulltidsresultat.
    """

    return (
        match.get("status") == "finished"
        and match.get("home_goals_ft") is not None
        and match.get("away_goals_ft") is not None
    )


def calculate_knockout_match_points(
    prediction: dict,
    match: dict,
) -> dict:
    """
    Räknar poäng för ett slutspelstips på en match.

    Poäng:
    - rätt 1/X/2 efter fulltid: 1p
    - rätt över/under 2,5 mål efter fulltid: 1p
    - rätt exakt resultat efter fulltid: 2p
    - rätt första målskytt: 4p

    Första målskytt bedöms manuellt via first_scorer_correct.
    """

    home_goals = int(match["home_goals_ft"])
    away_goals = int(match["away_goals_ft"])

    predicted_home_goals = int(prediction["predicted_home_goals"])
    predicted_away_goals = int(prediction["predicted_away_goals"])

    correct_outcome = get_match_outcome(home_goals, away_goals)
    predicted_outcome = get_match_outcome(
        predicted_home_goals,
        predicted_away_goals,
    )

    correct_goals_pick = get_goals_pick(home_goals, away_goals)

    outcome_points = 1 if predicted_outcome == correct_outcome else 0
    goals_points = 1 if prediction["goals_pick"] == correct_goals_pick else 0

    exact_result_points = (
        2
        if (
            predicted_home_goals == home_goals
            and predicted_away_goals == away_goals
        )
        else 0
    )

    first_scorer_points = (
        4
        if prediction.get("first_scorer_correct") is True
        else 0
    )

    return {
        "points": (
            outcome_points
            + goals_points
            + exact_result_points
            + first_scorer_points
        ),
        "outcome_points": outcome_points,
        "goals_points": goals_points,
        "exact_result_points": exact_result_points,
        "first_scorer_points": first_scorer_points,
    }