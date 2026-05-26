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

def calculate_knockout_final_points(
    final_prediction: dict | None,
) -> dict:
    """
    Räknar poäng för finaltips.

    Finaltips bedöms manuellt av admin:
    - correct_finalists_count: 0, 1 eller 2
    - winner_correct: True/False

    Poäng:
    - 5 poäng per rätt finallag
    - 10 poäng för rätt finalvinnare
    """

    if final_prediction is None:
        return {
            "points": 0,
            "finalist_points": 0,
            "winner_points": 0,
            "correct_finalists_count": 0,
            "winner_correct_count": 0,
        }

    correct_finalists_count = final_prediction.get(
        "correct_finalists_count"
    )

    if correct_finalists_count is None:
        correct_finalists_count = 0

    correct_finalists_count = int(correct_finalists_count)

    winner_correct = final_prediction.get("winner_correct") is True

    finalist_points = correct_finalists_count * 5
    winner_points = 10 if winner_correct else 0

    return {
        "points": finalist_points + winner_points,
        "finalist_points": finalist_points,
        "winner_points": winner_points,
        "correct_finalists_count": correct_finalists_count,
        "winner_correct_count": 1 if winner_correct else 0,
    }

def build_knockout_leaderboard(
    participants: list[dict],
    matches: list[dict],
    predictions: list[dict],
    final_predictions: list[dict] | None = None,
) -> list[dict]:
    """
    Bygger slutspels-poängtabell.

    Poängen räknas bara på slutspelsmatcher som har fulltidsresultat.

    Sortering:
    1. Poäng
    2. Flest exakta resultat
    3. Flest rätt 1/X/2
    4. Flest rätt första målskytt
    5. Namn
    """

    finished_matches = [
        match for match in matches
        if is_finished_knockout_match(match)
    ]

    finished_matches_by_id = {
        match["id"]: match
        for match in finished_matches
    }

    final_predictions = final_predictions or []

    final_prediction_by_participant_id = {
        final_prediction["participant_id"]: final_prediction
        for final_prediction in final_predictions
    }

    leaderboard_by_participant_id = {}

    for participant in participants:
        participant_id = participant["id"]

        leaderboard_by_participant_id[participant_id] = {
            "participant_id": participant_id,
            "Namn": participant["display_name"],
            "Poäng": 0,
            "Finalpoäng": 0,
            "Rätt finallag": 0,
            "Rätt finalvinnare": 0,
            "Rätt 1X2": 0,
            "Rätt Ö/U": 0,
            "Exakta resultat": 0,
            "Rätt första målskytt": 0,
            "Räknade matcher": len(finished_matches),
            "Maxpoäng just nu": len(finished_matches) * 8,
        }

    for prediction in predictions:
        participant_id = prediction["participant_id"]
        match_id = prediction["match_id"]

        if participant_id not in leaderboard_by_participant_id:
            continue

        match = finished_matches_by_id.get(match_id)

        if match is None:
            continue

        score = calculate_knockout_match_points(
            prediction=prediction,
            match=match,
        )

        row = leaderboard_by_participant_id[participant_id]

        row["Poäng"] += score["points"]
        row["Rätt 1X2"] += score["outcome_points"]
        row["Rätt Ö/U"] += score["goals_points"]

        if score["exact_result_points"] > 0:
            row["Exakta resultat"] += 1

        if score["first_scorer_points"] > 0:
            row["Rätt första målskytt"] += 1


    for participant_id, row in leaderboard_by_participant_id.items():
        final_prediction = final_prediction_by_participant_id.get(
            participant_id
        )

        final_score = calculate_knockout_final_points(final_prediction)

        row["Poäng"] += final_score["points"]
        row["Finalpoäng"] = final_score["points"]
        row["Rätt finallag"] = final_score["correct_finalists_count"]
        row["Rätt finalvinnare"] = final_score["winner_correct_count"]

        # När finaltips är bedömda blir maxpoängen +20.
        # Detta är en förenkling: maxpoäng just nu visar max från spelade
        # slutspelsmatcher plus finalbonus när finaltips finns/bedöms.
        if final_prediction is not None:
            row["Maxpoäng just nu"] += 20

    leaderboard = list(leaderboard_by_participant_id.values())

    leaderboard.sort(
        key=lambda row: (
            -row["Poäng"],
            -row["Exakta resultat"],
            -row["Rätt 1X2"],
            -row["Rätt första målskytt"],
            row["Namn"].lower(),
        )
    )

    previous_tiebreak_key = None
    previous_placement = 0

    for index, row in enumerate(leaderboard, start=1):
        current_tiebreak_key = (
            row["Poäng"],
            row["Exakta resultat"],
            row["Rätt 1X2"],
            row["Rätt första målskytt"],
        )

        if current_tiebreak_key == previous_tiebreak_key:
            row["Placering"] = previous_placement
        else:
            row["Placering"] = index
            previous_placement = index
            previous_tiebreak_key = current_tiebreak_key

    return leaderboard