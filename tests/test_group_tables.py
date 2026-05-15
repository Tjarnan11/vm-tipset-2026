from src.group_tables import build_group_tables


def test_build_group_table_with_one_finished_match():
    matches = [
        {
            "group_name": "A",
            "home_team": "Mexiko",
            "away_team": "Sydafrika",
            "home_goals": 2,
            "away_goals": 1,
            "status": "finished",
        },
        {
            "group_name": "A",
            "home_team": "Sydkorea",
            "away_team": "Tjeckien",
            "home_goals": None,
            "away_goals": None,
            "status": "scheduled",
        },
    ]

    group_tables = build_group_tables(matches)

    group_a = group_tables["A"]

    mexico = next(row for row in group_a if row["Lag"] == "Mexiko")
    south_africa = next(row for row in group_a if row["Lag"] == "Sydafrika")
    south_korea = next(row for row in group_a if row["Lag"] == "Sydkorea")

    assert mexico["M"] == 1
    assert mexico["V"] == 1
    assert mexico["GM"] == 2
    assert mexico["IM"] == 1
    assert mexico["MS"] == 1
    assert mexico["P"] == 3

    assert south_africa["M"] == 1
    assert south_africa["F"] == 1
    assert south_africa["GM"] == 1
    assert south_africa["IM"] == 2
    assert south_africa["MS"] == -1
    assert south_africa["P"] == 0

    # Lag utan färdigspelad match ska ändå synas i tabellen.
    assert south_korea["M"] == 0
    assert south_korea["P"] == 0


def test_build_group_table_draw():
    matches = [
        {
            "group_name": "B",
            "home_team": "Kanada",
            "away_team": "Schweiz",
            "home_goals": 1,
            "away_goals": 1,
            "status": "finished",
        },
    ]

    group_tables = build_group_tables(matches)

    group_b = group_tables["B"]

    canada = next(row for row in group_b if row["Lag"] == "Kanada")
    switzerland = next(row for row in group_b if row["Lag"] == "Schweiz")

    assert canada["M"] == 1
    assert canada["O"] == 1
    assert canada["P"] == 1
    assert canada["GM"] == 1
    assert canada["IM"] == 1
    assert canada["MS"] == 0

    assert switzerland["M"] == 1
    assert switzerland["O"] == 1
    assert switzerland["P"] == 1
    assert switzerland["GM"] == 1
    assert switzerland["IM"] == 1
    assert switzerland["MS"] == 0


def test_group_table_sorting_by_points_goal_difference_goals_scored():
    matches = [
        {
            "group_name": "C",
            "home_team": "Lag A",
            "away_team": "Lag B",
            "home_goals": 3,
            "away_goals": 0,
            "status": "finished",
        },
        {
            "group_name": "C",
            "home_team": "Lag C",
            "away_team": "Lag D",
            "home_goals": 2,
            "away_goals": 0,
            "status": "finished",
        },
    ]

    group_tables = build_group_tables(matches)

    group_c = group_tables["C"]

    assert group_c[0]["Lag"] == "Lag A"
    assert group_c[1]["Lag"] == "Lag C"