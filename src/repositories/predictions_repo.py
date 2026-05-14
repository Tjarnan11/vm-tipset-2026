# src/repositories/predictions_repo.py
#
# Databasfunktioner för deltagarnas tips.
#
# Den här filen ansvarar för:
# - hämta en deltagares sparade tips
# - spara/uppdatera tips för flera matcher
#
# Själva Streamlit-UI:t ska inte behöva veta exakt hur databasen fungerar.

from datetime import datetime, timezone

from src.db import get_supabase_client


def get_predictions_for_participant(participant_id: str) -> list[dict]:
    """
    Hämtar alla sparade tips för en deltagare.

    Returnerar exempelvis:
    [
        {
            "participant_id": "...",
            "match_id": "...",
            "outcome_pick": "1",
            "goals_pick": "over"
        }
    ]
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("predictions")
        .select("participant_id, match_id, outcome_pick, goals_pick, updated_at")
        .eq("participant_id", participant_id)
        .execute()
    )

    return response.data


def save_predictions(participant_id: str, predictions: list[dict]) -> list[dict]:
    """
    Sparar flera tips för en deltagare.

    predictions ska vara en lista med dictionaries:
    [
        {
            "match_id": "...",
            "outcome_pick": "1",
            "goals_pick": "over"
        }
    ]

    Vi använder upsert:
    - om tipset inte finns: skapa ny rad
    - om tipset redan finns: uppdatera befintlig rad

    Detta fungerar eftersom databasen har:
        unique(participant_id, match_id)
    """

    if not predictions:
        return []

    supabase = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()

    rows_to_save = []

    for prediction in predictions:
        rows_to_save.append(
            {
                "participant_id": participant_id,
                "match_id": prediction["match_id"],
                "outcome_pick": prediction["outcome_pick"],
                "goals_pick": prediction["goals_pick"],
                "updated_at": now,
            }
        )

    response = (
        supabase.table("predictions")
        .upsert(rows_to_save, on_conflict="participant_id,match_id")
        .execute()
    )

    return response.data

def delete_predictions_for_matches(
    participant_id: str,
    match_ids: list[str],
) -> None:
    """
    Tar bort sparade tips för en deltagare för valda matcher.

    Används när deltagaren har valt "Välj" på både 1/X/2 och över/under.
    Då betyder det att tipset ska rensas.
    """

    if not match_ids:
        return

    supabase = get_supabase_client()

    (
        supabase.table("predictions")
        .delete()
        .eq("participant_id", participant_id)
        .in_("match_id", match_ids)
        .execute()
    )

def get_all_predictions() -> list[dict]:
    """
    Hämtar alla sparade tips.

    Används för poängtabellen.

    Viktigt:
    Vi visar inte automatiskt alla tips för deltagare före deadline.
    Den här funktionen hämtar bara data till server-side poängberäkning.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("predictions")
        .select("participant_id, match_id, outcome_pick, goals_pick")
        .execute()
    )

    return response.data