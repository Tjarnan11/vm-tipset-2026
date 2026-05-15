from src.scoring import (
    calculate_prediction_points,
    get_goals_pick,
    get_match_outcome,
    is_finished_match,
)

from src.scoring import build_leaderboard


def test_get_match_outcome_home_win():
    assert get_match_outcome(2, 1) == "1"


def test_get_match_outcome_draw():
    assert get_match_outcome(1, 1) == "X"


def test_get_match_outcome_away_win():
    assert get_match_outcome(0, 2) == "2"


def test_get_goals_pick_over():
    assert get_goals_pick(2, 1) == "over"


def test_get_goals_pick_under():
    assert get_goals_pick(1, 1) == "under"


def test_is_finished_match_true():
    match = {
        "status": "finished",
        "home_goals": 2,
        "away_goals": 1,
    }

    assert is_finished_match(match) is True


def test_is_finished_match_false_when_missing_goals():
    match = {
        "status": "finished",
        "home_goals": None,
        "away_goals": 1,
    }

    assert is_finished_match(match) is False


def test_calculate_prediction_points_full_score():
    prediction = {
        "outcome_pick": "1",
        "goals_pick": "over",
    }

    match = {
        "home_goals": 2,
        "away_goals": 1,
    }

    score = calculate_prediction_points(prediction, match)

    assert score["points"] == 2
    assert score["outcome_points"] == 1
    assert score["goals_points"] == 1


def test_calculate_prediction_points_one_point():
    prediction = {
        "outcome_pick": "X",
        "goals_pick": "over",
    }

    match = {
        "home_goals": 2,
        "away_goals": 1,
    }

    score = calculate_prediction_points(prediction, match)

    assert score["points"] == 1
    assert score["outcome_points"] == 0
    assert score["goals_points"] == 1


def test_calculate_prediction_points_zero_points():
    prediction = {
        "outcome_pick": "2",
        "goals_pick": "under",
    }

    match = {
        "home_goals": 2,
        "away_goals": 1,
    }

    score = calculate_prediction_points(prediction, match)

    assert score["points"] == 0
    assert score["outcome_points"] == 0
    assert score["goals_points"] == 0

    




def test_build_leaderboard_shared_placement_when_fully_tied():
    participants = [
        {"id": "p1", "display_name": "Anna"},
        {"id": "p2", "display_name": "Erik"},
        {"id": "p3", "display_name": "Jocke"},
    ]

    matches = [
        {
            "id": "m1",
            "status": "finished",
            "home_goals": 2,
            "away_goals": 1,
        }
    ]

    predictions = [
        {
            "participant_id": "p1",
            "match_id": "m1",
            "outcome_pick": "1",
            "goals_pick": "over",
        },
        {
            "participant_id": "p2",
            "match_id": "m1",
            "outcome_pick": "1",
            "goals_pick": "over",
        },
        {
            "participant_id": "p3",
            "match_id": "m1",
            "outcome_pick": "X",
            "goals_pick": "over",
        },
    ]

    leaderboard = build_leaderboard(
        participants=participants,
        matches=matches,
        predictions=predictions,
    )

    anna = next(row for row in leaderboard if row["Namn"] == "Anna")
    erik = next(row for row in leaderboard if row["Namn"] == "Erik")
    jocke = next(row for row in leaderboard if row["Namn"] == "Jocke")

    assert anna["Placering"] == 1
    assert erik["Placering"] == 1
    assert jocke["Placering"] == 3