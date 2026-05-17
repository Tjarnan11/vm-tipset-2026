from src.knockout_scoring import (
    calculate_knockout_match_points,
    get_knockout_prediction_outcome,
    is_finished_knockout_match,
)


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