from src.ui.knockout_stats import (
    _build_goal_total_rows,
    _build_public_prediction_rows,
    _get_public_knockout_predictions,
    _get_public_match_ids,
    _get_public_round_ids,
)


def test_get_public_round_ids_excludes_future_open_round(monkeypatch):
    monkeypatch.setattr(
        "src.ui.knockout_stats.is_deadline_passed",
        lambda deadline_at: deadline_at == "past",
    )

    rounds = [
        {
            "id": "round_1",
            "status": "open",
            "deadline_at": "past",
        },
        {
            "id": "round_2",
            "status": "open",
            "deadline_at": "future",
        },
        {
            "id": "round_3",
            "status": "locked",
            "deadline_at": "future",
        },
        {
            "id": "round_4",
            "status": "not_started",
            "deadline_at": None,
        },
    ]

    assert _get_public_round_ids(rounds) == {"round_1", "round_3"}


def test_build_public_prediction_rows_filters_non_public_rounds():
    participants = [
        {
            "id": "participant_1",
            "display_name": "Ada",
        }
    ]

    matches = [
        {
            "id": "match_1",
            "round_id": "public_round",
            "match_no": 1,
            "home_team": "Sweden",
            "away_team": "Norway",
            "knockout_rounds": {
                "name": "Åttondel",
            },
        },
        {
            "id": "match_2",
            "round_id": "future_round",
            "match_no": 2,
            "home_team": "Denmark",
            "away_team": "Finland",
            "knockout_rounds": {
                "name": "Kvart",
            },
        },
    ]

    predictions = [
        {
            "participant_id": "participant_1",
            "match_id": "match_1",
            "predicted_home_goals": 2,
            "predicted_away_goals": 1,
            "goals_pick": "over",
            "first_scorer_pick": "Ada",
        },
        {
            "participant_id": "participant_1",
            "match_id": "match_2",
            "predicted_home_goals": 0,
            "predicted_away_goals": 1,
            "goals_pick": "under",
            "first_scorer_pick": "Grace",
        },
    ]

    rows = _build_public_prediction_rows(
        participants=participants,
        matches=matches,
        predictions=predictions,
        public_round_ids={"public_round"},
    )

    assert len(rows) == 1
    assert rows[0]["match_id"] == "match_1"
    assert rows[0]["outcome"] == "1"
    assert rows[0]["exact_result"] == "2-1"


def test_get_public_match_ids_excludes_future_round_matches():
    matches = [
        {
            "id": "match_1",
            "round_id": "public_round",
        },
        {
            "id": "match_2",
            "round_id": "future_round",
        },
    ]

    assert _get_public_match_ids(matches, {"public_round"}) == ["match_1"]


def test_get_public_knockout_predictions_fetches_only_public_match_ids(monkeypatch):
    fetched_match_ids = []

    def fake_get_predictions(match_ids):
        fetched_match_ids.extend(match_ids)
        return []

    monkeypatch.setattr(
        "src.ui.knockout_stats.get_knockout_predictions_for_matches",
        fake_get_predictions,
    )

    matches = [
        {
            "id": "match_1",
            "round_id": "public_round",
        },
        {
            "id": "match_2",
            "round_id": "future_round",
        },
    ]

    predictions = _get_public_knockout_predictions(
        matches,
        {"public_round"},
    )

    assert predictions == []
    assert fetched_match_ids == ["match_1"]


def test_build_goal_total_rows_counts_only_finished_public_matches():
    participants = [
        {
            "id": "participant_1",
            "display_name": "Ada",
        }
    ]

    matches = [
        {
            "id": "match_1",
            "round_id": "public_round",
            "match_no": 1,
            "home_team": "Sweden",
            "away_team": "Norway",
            "home_goals_ft": 2,
            "away_goals_ft": 1,
            "status": "finished",
            "knockout_rounds": {
                "name": "Åttondel",
            },
        },
        {
            "id": "match_2",
            "round_id": "public_round",
            "match_no": 2,
            "home_team": "Denmark",
            "away_team": "Finland",
            "home_goals_ft": None,
            "away_goals_ft": None,
            "status": "scheduled",
            "knockout_rounds": {
                "name": "Åttondel",
            },
        },
        {
            "id": "match_3",
            "round_id": "future_round",
            "match_no": 3,
            "home_team": "Spain",
            "away_team": "France",
            "home_goals_ft": 1,
            "away_goals_ft": 1,
            "status": "finished",
            "knockout_rounds": {
                "name": "Kvart",
            },
        },
    ]

    predictions = [
        {
            "participant_id": "participant_1",
            "match_id": "match_1",
            "predicted_home_goals": 3,
            "predicted_away_goals": 1,
        },
        {
            "participant_id": "participant_1",
            "match_id": "match_2",
            "predicted_home_goals": 4,
            "predicted_away_goals": 4,
        },
        {
            "participant_id": "participant_1",
            "match_id": "match_3",
            "predicted_home_goals": 0,
            "predicted_away_goals": 0,
        },
    ]

    rows = _build_goal_total_rows(
        participants=participants,
        matches=matches,
        predictions=predictions,
        public_round_ids={"public_round"},
    )

    assert len(rows) == 1
    assert rows[0]["match_id"] == "match_1"
    assert rows[0]["Tippade mål"] == 4
    assert rows[0]["Faktiska mål"] == 3
    assert rows[0]["Skillnad"] == 1
