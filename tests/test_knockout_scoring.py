from src.knockout_scoring import (
    calculate_knockout_match_points,
    get_knockout_prediction_outcome,
    is_finished_knockout_match,
    calculate_knockout_final_points,
)

from src.knockout_scoring import build_knockout_leaderboard


def test_get_knockout_prediction_outcome_home_win():
    assert get_knockout_prediction_outcome(2, 1) == "1"


def test_get_knockout_prediction_outcome_draw():
    assert get_knockout_prediction_outcome(1, 1) == "X"


def test_get_knockout_prediction_outcome_away_win():
    assert get_knockout_prediction_outcome(0, 2) == "2"


def test_is_finished_knockout_match_true():
    match = {
        "status": "finished",
        "home_goals_ft": 2,
        "away_goals_ft": 1,
    }

    assert is_finished_knockout_match(match) is True


def test_calculate_knockout_match_points_full_match_without_scorer():
    prediction = {
        "predicted_home_goals": 2,
        "predicted_away_goals": 1,
        "goals_pick": "over",
        "first_scorer_correct": False,
    }

    match = {
        "home_goals_ft": 2,
        "away_goals_ft": 1,
    }

    score = calculate_knockout_match_points(prediction, match)

    assert score["points"] == 4
    assert score["outcome_points"] == 1
    assert score["goals_points"] == 1
    assert score["exact_result_points"] == 2
    assert score["first_scorer_points"] == 0


def test_calculate_knockout_match_points_with_first_scorer():
    prediction = {
        "predicted_home_goals": 2,
        "predicted_away_goals": 1,
        "goals_pick": "over",
        "first_scorer_correct": True,
    }

    match = {
        "home_goals_ft": 2,
        "away_goals_ft": 1,
    }

    score = calculate_knockout_match_points(prediction, match)

    assert score["points"] == 8
    assert score["first_scorer_points"] == 4


def test_calculate_knockout_match_points_partial():
    prediction = {
        "predicted_home_goals": 3,
        "predicted_away_goals": 1,
        "goals_pick": "over",
        "first_scorer_correct": False,
    }

    match = {
        "home_goals_ft": 1,
        "away_goals_ft": 0,
    }

    score = calculate_knockout_match_points(prediction, match)

    assert score["points"] == 1
    assert score["outcome_points"] == 1
    assert score["goals_points"] == 0
    assert score["exact_result_points"] == 0
    assert score["first_scorer_points"] == 0




def test_build_knockout_leaderboard():
    participants = [
        {"id": "p1", "display_name": "Anna"},
        {"id": "p2", "display_name": "Erik"},
    ]

    matches = [
        {
            "id": "m1",
            "status": "finished",
            "home_goals_ft": 2,
            "away_goals_ft": 1,
        }
    ]

    predictions = [
        {
            "participant_id": "p1",
            "match_id": "m1",
            "predicted_home_goals": 2,
            "predicted_away_goals": 1,
            "goals_pick": "over",
            "first_scorer_correct": False,
        },
        {
            "participant_id": "p2",
            "match_id": "m1",
            "predicted_home_goals": 1,
            "predicted_away_goals": 0,
            "goals_pick": "under",
            "first_scorer_correct": False,
        },
    ]

    leaderboard = build_knockout_leaderboard(
        participants=participants,
        matches=matches,
        predictions=predictions,
    )

    anna = next(row for row in leaderboard if row["Namn"] == "Anna")
    erik = next(row for row in leaderboard if row["Namn"] == "Erik")

    assert anna["Poäng"] == 4
    assert anna["Rätt 1X2"] == 1
    assert anna["Rätt Ö/U"] == 1
    assert anna["Exakta resultat"] == 1
    assert anna["Placering"] == 1

    assert erik["Poäng"] == 1
    assert erik["Rätt 1X2"] == 1
    assert erik["Rätt Ö/U"] == 0
    assert erik["Exakta resultat"] == 0
    assert erik["Placering"] == 2

def test_calculate_knockout_final_points_none():
    score = calculate_knockout_final_points(None)

    assert score["points"] == 0
    assert score["finalist_points"] == 0
    assert score["winner_points"] == 0


def test_calculate_knockout_final_points_full_score():
    final_prediction = {
        "correct_finalists_count": 2,
        "winner_correct": True,
    }

    score = calculate_knockout_final_points(final_prediction)

    assert score["points"] == 20
    assert score["finalist_points"] == 10
    assert score["winner_points"] == 10
    assert score["correct_finalists_count"] == 2
    assert score["winner_correct_count"] == 1


def test_build_knockout_leaderboard_with_final_points():
    participants = [
        {"id": "p1", "display_name": "Anna"},
        {"id": "p2", "display_name": "Erik"},
    ]

    matches = []

    predictions = []

    final_predictions = [
        {
            "participant_id": "p1",
            "correct_finalists_count": 2,
            "winner_correct": True,
        },
        {
            "participant_id": "p2",
            "correct_finalists_count": 1,
            "winner_correct": False,
        },
    ]

    leaderboard = build_knockout_leaderboard(
        participants=participants,
        matches=matches,
        predictions=predictions,
        final_predictions=final_predictions,
    )

    anna = next(row for row in leaderboard if row["Namn"] == "Anna")
    erik = next(row for row in leaderboard if row["Namn"] == "Erik")

    assert anna["Poäng"] == 20
    assert anna["Finalpoäng"] == 20
    assert anna["Rätt finallag"] == 2
    assert anna["Rätt finalvinnare"] == 1
    assert anna["Placering"] == 1

    assert erik["Poäng"] == 5
    assert erik["Finalpoäng"] == 5
    assert erik["Rätt finallag"] == 1
    assert erik["Rätt finalvinnare"] == 0
    assert erik["Placering"] == 2