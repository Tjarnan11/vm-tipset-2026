# src/repositories/knockout_repo.py
#
# Databasfunktioner för slutspelstipset.
#
# Slutspel byggs som en separat tävlingsdel i samma app:
# - egna rundor
# - egna matcher
# - egna tips
# - egen poängtabell senare

from datetime import datetime, timezone

from src.db import get_supabase_client


def get_knockout_rounds() -> list[dict]:
    """
    Hämtar slutspelsrundor i rätt ordning.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_rounds")
        .select("id, name, sort_order, deadline_at, status, created_at")
        .order("sort_order")
        .execute()
    )

    return response.data


def update_knockout_round(
    round_id: str,
    deadline_at: str | None,
    status: str,
) -> dict | None:
    """
    Uppdaterar deadline och status för en slutspelsrunda.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_rounds")
        .update(
            {
                "deadline_at": deadline_at,
                "status": status,
            }
        )
        .eq("id", round_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def get_knockout_matches() -> list[dict]:
    """
    Hämtar alla slutspelsmatcher.

    Vi hämtar även runda via relationen knockout_rounds.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_matches")
        .select(
            "id, round_id, match_no, kickoff_at, home_team, away_team, "
            "home_placeholder, away_placeholder, first_scorer, "
            "home_goals_ft, away_goals_ft, status, created_at, "
            "knockout_rounds(name, sort_order, status, deadline_at)"
        )
        .order("match_no")
        .execute()
    )

    return response.data


def get_knockout_matches_for_round(round_id: str) -> list[dict]:
    """
    Hämtar slutspelsmatcher för en specifik runda.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_matches")
        .select(
            "id, round_id, match_no, kickoff_at, home_team, away_team, "
            "home_placeholder, away_placeholder, first_scorer, "
            "home_goals_ft, away_goals_ft, status, created_at"
        )
        .eq("round_id", round_id)
        .order("match_no")
        .execute()
    )

    return response.data


def upsert_knockout_match(match: dict) -> dict | None:
    """
    Skapar eller uppdaterar en slutspelsmatch.

    match_no används som stabil nyckel.

    För MVP fyller admin lag manuellt.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_matches")
        .upsert(match, on_conflict="match_no")
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def update_knockout_match_result(
    match_id: str,
    home_goals_ft: int,
    away_goals_ft: int,
) -> dict | None:
    """
    Sparar fulltidsresultat för en slutspelsmatch.

    Fulltid = 90 minuter + tillägg.
    Ej förlängning eller straffar.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_matches")
        .update(
            {
                "home_goals_ft": home_goals_ft,
                "away_goals_ft": away_goals_ft,
                "status": "finished",
            }
        )
        .eq("id", match_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def clear_knockout_match_result(match_id: str) -> dict | None:
    """
    Rensar resultat för en slutspelsmatch.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_matches")
        .update(
            {
                "home_goals_ft": None,
                "away_goals_ft": None,
                "status": "scheduled",
            }
        )
        .eq("id", match_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def get_knockout_predictions_for_participant(
    participant_id: str,
) -> list[dict]:
    """
    Hämtar en deltagares slutspelstips.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_predictions")
        .select(
            "id, participant_id, match_id, predicted_home_goals, "
            "predicted_away_goals, goals_pick, first_scorer_pick, "
            "first_scorer_correct, updated_at"
        )
        .eq("participant_id", participant_id)
        .execute()
    )

    return response.data


def get_all_knockout_predictions() -> list[dict]:
    """
    Hämtar alla slutspelstips.

    Ska bara visas/exporteras efter relevant deadline.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_predictions")
        .select(
            "id, participant_id, match_id, predicted_home_goals, "
            "predicted_away_goals, goals_pick, first_scorer_pick, "
            "first_scorer_correct, updated_at"
        )
        .execute()
    )

    return response.data


def save_knockout_predictions(
    participant_id: str,
    predictions: list[dict],
) -> list[dict]:
    """
    Sparar flera slutspelstips för en deltagare.

    Varje prediction ska innehålla:
    - match_id
    - predicted_home_goals
    - predicted_away_goals
    - goals_pick
    - first_scorer_pick
    """

    if not predictions:
        return []

    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    rows = []

    for prediction in predictions:
        rows.append(
            {
                "participant_id": participant_id,
                "match_id": prediction["match_id"],
                "predicted_home_goals": prediction["predicted_home_goals"],
                "predicted_away_goals": prediction["predicted_away_goals"],
                "goals_pick": prediction["goals_pick"],
                "first_scorer_pick": prediction["first_scorer_pick"],
                "updated_at": now,
            }
        )

    response = (
        supabase.table("knockout_predictions")
        .upsert(rows, on_conflict="participant_id,match_id")
        .execute()
    )

    return response.data


def update_first_scorer_correct(
    prediction_id: str,
    first_scorer_correct: bool | None,
) -> dict | None:
    """
    Admin markerar om ett första-målskytt-tips är rätt eller fel.

    None betyder ej bedömt.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_predictions")
        .update({"first_scorer_correct": first_scorer_correct})
        .eq("id", prediction_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def get_knockout_final_prediction_for_participant(
    participant_id: str,
) -> dict | None:
    """
    Hämtar en deltagares finaltips.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_final_predictions")
        .select(
            "participant_id, finalist_1, finalist_2, winner, "
            "correct_finalists_count, winner_correct, updated_at"
        )
        .eq("participant_id", participant_id)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None

def save_knockout_final_prediction(
    participant_id: str,
    finalist_1: str,
    finalist_2: str,
    winner: str,
) -> dict | None:
    """
    Sparar deltagarens långtidstips för finalen.
    """

    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("knockout_final_predictions")
        .upsert(
            {
                "participant_id": participant_id,
                "finalist_1": finalist_1.strip(),
                "finalist_2": finalist_2.strip(),
                "winner": winner.strip(),
                "updated_at": now,
            },
            on_conflict="participant_id",
        )
        .execute()
    )

    if response.data:
        return response.data[0]

    return None

def delete_knockout_final_prediction(participant_id: str) -> bool:
    """
    Tar bort en deltagares finaltips.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_final_predictions")
        .delete()
        .eq("participant_id", participant_id)
        .execute()
    )

    return response is not None

def get_all_knockout_final_predictions() -> list[dict]:
    """
    Hämtar alla finaltips.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_final_predictions")
        .select(
            "participant_id, finalist_1, finalist_2, winner, "
            "correct_finalists_count, winner_correct, updated_at"
        )
        .execute()
    )

    return response.data


def get_knockout_final_result() -> dict | None:
    """
    Hämtar faktiskt finalutfall.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_final_result")
        .select("id, finalist_1, finalist_2, winner, updated_at")
        .eq("id", 1)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def save_knockout_final_result(
    finalist_1: str,
    finalist_2: str,
    winner: str,
) -> dict | None:
    """
    Sparar faktiskt finalutfall.

    Tabellen ska bara ha en rad med id = 1.
    """

    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("knockout_final_result")
        .upsert(
            {
                "id": 1,
                "finalist_1": finalist_1.strip(),
                "finalist_2": finalist_2.strip(),
                "winner": winner.strip(),
                "updated_at": now,
            },
            on_conflict="id",
        )
        .execute()
    )

    if response.data:
        return response.data[0]

    return None

def get_knockout_round_by_name(round_name: str) -> dict | None:
    """
    Hämtar en slutspelsrunda baserat på namn.

    Används vid CSV-import där CSV-filen innehåller round_name.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_rounds")
        .select("id, name, sort_order, deadline_at, status, created_at")
        .eq("name", round_name)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None

def update_knockout_final_prediction_review(
    participant_id: str,
    correct_finalists_count: int | None,
    winner_correct: bool | None,
) -> dict | None:
    """
    Admin bedömer en deltagares finaltips manuellt.

    correct_finalists_count:
        None = ej bedömt
        0, 1 eller 2 = antal rätt finallag

    winner_correct:
        None = ej bedömt
        True = rätt vinnare
        False = fel vinnare
    """

    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("knockout_final_predictions")
        .update(
            {
                "correct_finalists_count": correct_finalists_count,
                "winner_correct": winner_correct,
                "updated_at": now,
            }
        )
        .eq("participant_id", participant_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None

def update_knockout_match_teams(
    match_id: str,
    home_team: str,
    away_team: str,
) -> dict | None:
    """
    Uppdaterar bara lagen i en slutspelsmatch.

    Används när placeholders ska ersättas med faktiska lag.
    Ändrar inte avsparkstid, runda, matchnummer eller resultat.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("knockout_matches")
        .update(
            {
                "home_team": home_team,
                "away_team": away_team,
            }
        )
        .eq("id", match_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None

def update_knockout_match_first_scorer(
    match_id: str,
    first_scorer: str | None,
) -> dict | None:
    """
    Sparar faktisk första målskytt för en slutspelsmatch.

    Detta används för visning. Poäng ges fortfarande via manuell
    bedömning av varje deltagares målskyttstips.
    """

    supabase = get_supabase_client()

    cleaned_first_scorer = (
        first_scorer.strip()
        if first_scorer
        else None
    )

    response = (
        supabase.table("knockout_matches")
        .update(
            {
                "first_scorer": cleaned_first_scorer,
            }
        )
        .eq("id", match_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None