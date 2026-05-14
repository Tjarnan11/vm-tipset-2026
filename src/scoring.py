# src/scoring.py
#
# Den här filen innehåller ren poänglogik.
#
# Det är bra att hålla poänglogiken separat från Streamlit-UI:t.
# Då blir det enklare att:
# - förstå reglerna
# - testa poängräkningen senare
# - ändra regler utan att röra admin/deltagar-sidorna


def get_match_outcome(home_goals: int, away_goals: int) -> str:
    """
    Räknar ut 1/X/2 för ett färdigt matchresultat.

    Returnerar:
        "1" om hemmalaget vann
        "X" om matchen blev oavgjord
        "2" om bortalaget vann
    """

    if home_goals > away_goals:
        return "1"

    if home_goals < away_goals:
        return "2"

    return "X"


def get_goals_pick(home_goals: int, away_goals: int) -> str:
    """
    Räknar ut om matchen gick över eller under 2,5 mål.

    Eftersom fotbollsmål är heltal betyder:
        0, 1 eller 2 mål totalt = under
        3 eller fler mål totalt = over
    """

    total_goals = home_goals + away_goals

    if total_goals > 2.5:
        return "over"

    return "under"


def is_finished_match(match: dict) -> bool:
    """
    Kontrollerar om en match ska räknas i poängtabellen.

    Vi kräver både:
    - status == "finished"
    - att båda målkolumnerna faktiskt har värden
    """

    return (
        match.get("status") == "finished"
        and match.get("home_goals") is not None
        and match.get("away_goals") is not None
    )


def calculate_prediction_points(prediction: dict, match: dict) -> dict:
    """
    Räknar poäng för ett tips på en specifik match.

    Returnerar en dictionary med:
    - total points
    - om 1/X/2 var rätt
    - om över/under var rätt
    """

    home_goals = int(match["home_goals"])
    away_goals = int(match["away_goals"])

    correct_outcome = get_match_outcome(home_goals, away_goals)
    correct_goals_pick = get_goals_pick(home_goals, away_goals)

    outcome_points = 1 if prediction["outcome_pick"] == correct_outcome else 0
    goals_points = 1 if prediction["goals_pick"] == correct_goals_pick else 0

    return {
        "points": outcome_points + goals_points,
        "outcome_points": outcome_points,
        "goals_points": goals_points,
    }


def build_leaderboard(
    participants: list[dict],
    matches: list[dict],
    predictions: list[dict],
) -> list[dict]:
    """
    Bygger poängtabellen.

    Input:
        participants = aktiva deltagare
        matches = alla matcher
        predictions = alla sparade tips

    Output:
        lista med leaderboard-rader, sorterade efter poäng.

    Poängregler:
        +1 för rätt 1/X/2
        +1 för rätt över/under 2,5 mål
    """

    finished_matches = [
        match for match in matches
        if is_finished_match(match)
    ]

    finished_matches_by_id = {
        match["id"]: match
        for match in finished_matches
    }

    # Starta varje deltagare på 0 poäng.
    leaderboard_by_participant_id = {}

    for participant in participants:
        participant_id = participant["id"]

        leaderboard_by_participant_id[participant_id] = {
            "participant_id": participant_id,
            "Namn": participant["display_name"],
            "Poäng": 0,
            "Rätt 1X2": 0,
            "Rätt Ö/U": 0,
            "Räknade matcher": 0,
            "Maxpoäng just nu": len(finished_matches) * 2,
        }

    # Gå igenom alla tips.
    # Tips på matcher som inte är färdigspelade ignoreras.
    for prediction in predictions:
        participant_id = prediction["participant_id"]
        match_id = prediction["match_id"]

        if participant_id not in leaderboard_by_participant_id:
            continue

        if match_id not in finished_matches_by_id:
            continue

        match = finished_matches_by_id[match_id]
        score = calculate_prediction_points(prediction, match)

        row = leaderboard_by_participant_id[participant_id]

        row["Poäng"] += score["points"]
        row["Rätt 1X2"] += score["outcome_points"]
        row["Rätt Ö/U"] += score["goals_points"]
        row["Räknade matcher"] += 1

    leaderboard = list(leaderboard_by_participant_id.values())

    # Sortering:
    # 1. Högst poäng
    # 2. Flest rätt 1X2
    # 3. Flest rätt över/under
    # 4. Namn alfabetiskt
    leaderboard.sort(
        key=lambda row: (
            -row["Poäng"],
            -row["Rätt 1X2"],
            -row["Rätt Ö/U"],
            row["Namn"].lower(),
        )
    )

    # Lägg till placering.
    # För MVP kör vi enkel 1, 2, 3-ranking även om två är exakt lika.
    for index, row in enumerate(leaderboard, start=1):
        row["Placering"] = index

    return leaderboard