# src/group_tables.py
#
# Logik för att räkna fram gruppställningar från matchresultat.
#
# Vi räknar en enkel fotbollstabell:
# - 3 poäng för vinst
# - 1 poäng för oavgjort
# - målskillnad
# - gjorda mål
#
# Detta är tillräckligt för en tydlig MVP-översikt.
# Fullständig FIFA-tiebreaker-logik kan läggas till senare om vi vill.

from collections import defaultdict

from src.scoring import is_finished_match


def create_empty_team_row(team_name: str) -> dict:
    """
    Skapar en tom tabellrad för ett lag.
    """

    return {
        "Lag": team_name,
        "M": 0,
        "V": 0,
        "O": 0,
        "F": 0,
        "GM": 0,
        "IM": 0,
        "MS": 0,
        "P": 0,
    }


def build_group_tables(matches: list[dict]) -> dict[str, list[dict]]:
    """
    Bygger gruppställningar från matchlistan.

    Returnerar:
    {
        "A": [rad för lag 1, rad för lag 2, ...],
        "B": [...],
    }

    Även lag utan färdigspelade matcher visas, eftersom vi lägger till lag
    från alla matcher innan vi räknar resultat.
    """

    groups = defaultdict(dict)

    # Lägg först in alla lag från alla matcher.
    # Då visas även lag som ännu inte spelat någon match.
    for match in matches:
        group_name = match["group_name"]
        home_team = match["home_team"]
        away_team = match["away_team"]

        if home_team not in groups[group_name]:
            groups[group_name][home_team] = create_empty_team_row(home_team)

        if away_team not in groups[group_name]:
            groups[group_name][away_team] = create_empty_team_row(away_team)

    # Räkna resultat från färdigspelade matcher.
    for match in matches:
        if not is_finished_match(match):
            continue

        group_name = match["group_name"]
        home_team = match["home_team"]
        away_team = match["away_team"]

        home_goals = int(match["home_goals"])
        away_goals = int(match["away_goals"])

        home_row = groups[group_name][home_team]
        away_row = groups[group_name][away_team]

        home_row["M"] += 1
        away_row["M"] += 1

        home_row["GM"] += home_goals
        home_row["IM"] += away_goals

        away_row["GM"] += away_goals
        away_row["IM"] += home_goals

        if home_goals > away_goals:
            home_row["V"] += 1
            away_row["F"] += 1
            home_row["P"] += 3

        elif home_goals < away_goals:
            away_row["V"] += 1
            home_row["F"] += 1
            away_row["P"] += 3

        else:
            home_row["O"] += 1
            away_row["O"] += 1
            home_row["P"] += 1
            away_row["P"] += 1

    # Räkna målskillnad och sortera varje grupp.
    result = {}

    for group_name, teams_by_name in groups.items():
        rows = list(teams_by_name.values())

        for row in rows:
            row["MS"] = row["GM"] - row["IM"]

        rows.sort(
            key=lambda row: (
                -row["P"],
                -row["MS"],
                -row["GM"],
                row["Lag"].lower(),
            )
        )

        result[group_name] = rows

    return dict(sorted(result.items()))