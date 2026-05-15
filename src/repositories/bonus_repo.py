# src/repositories/bonus_repo.py
#
# Databasfunktioner för utslagsfrågan:
# "Vem gör flest mål i gruppspelet?"
#
# Deltagare väljer en spelare före deadline.
# Admin fyller senare i antal gruppspelsmål för valda spelare.

from datetime import datetime, timezone

from src.db import get_supabase_client


def get_bonus_prediction_for_participant(participant_id: str) -> dict | None:
    """
    Hämtar en deltagares svar på utslagsfrågan.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("bonus_predictions")
        .select("participant_id, scorer_name, updated_at")
        .eq("participant_id", participant_id)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def save_bonus_prediction(
    participant_id: str,
    scorer_name: str,
) -> dict | None:
    """
    Sparar eller uppdaterar deltagarens svar på utslagsfrågan.
    """

    supabase = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("bonus_predictions")
        .upsert(
            {
                "participant_id": participant_id,
                "scorer_name": scorer_name.strip(),
                "updated_at": now,
            },
            on_conflict="participant_id",
        )
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def delete_bonus_prediction(participant_id: str) -> None:
    """
    Tar bort deltagarens bonusval.

    Används om deltagaren rensar fältet före deadline.
    """

    supabase = get_supabase_client()

    (
        supabase.table("bonus_predictions")
        .delete()
        .eq("participant_id", participant_id)
        .execute()
    )


def get_all_bonus_predictions() -> list[dict]:
    """
    Hämtar alla deltagares bonusval.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("bonus_predictions")
        .select("participant_id, scorer_name, updated_at")
        .execute()
    )

    return response.data


def get_bonus_scorer_results() -> list[dict]:
    """
    Hämtar adminens målnoteringar för valda spelare.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("bonus_scorer_results")
        .select("scorer_name, goals, updated_at")
        .execute()
    )

    return response.data


def upsert_bonus_scorer_result(
    scorer_name: str,
    goals: int,
) -> dict | None:
    """
    Sparar antal gruppspelsmål för en vald spelare.
    """

    supabase = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("bonus_scorer_results")
        .upsert(
            {
                "scorer_name": scorer_name.strip(),
                "goals": goals,
                "updated_at": now,
            },
            on_conflict="scorer_name",
        )
        .execute()
    )

    if response.data:
        return response.data[0]

    return None