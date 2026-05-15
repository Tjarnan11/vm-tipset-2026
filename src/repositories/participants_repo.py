# src/repositories/participants_repo.py
#
# Repository betyder ungefär:
# "En plats där vi samlar databasfunktioner för en viss typ av data."
#
# Den här filen hanterar deltagare:
# - hämta deltagare
# - skapa deltagare
# - hitta deltagare via privat token
# - uppdatera/återskapa privat token

from src.auth import hash_token
from src.db import get_supabase_client


def get_active_participants() -> list[dict]:
    """
    Hämtar alla aktiva deltagare.

    Används av admin för att se vilka som finns.

    Vi hämtar private_token så att admin kan återskapa och exportera
    deltagarnas privata länkar.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("participants")
        .select(
            "id, display_name, private_token, "
            "is_active, created_at"
        )
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )

    return response.data


def create_participant(
    display_name: str,
    token: str,
) -> dict | None:
    """
    Skapar en ny deltagare.

    Vi sparar både:
    - token_hash: används för att identifiera deltagaren
    - private_token: används för att admin ska kunna visa länken igen

    Detta är praktiskt för MVP:n eftersom admin slipper hantera länkar manuellt.
    """

    supabase = get_supabase_client()

    token_hash = hash_token(token)

    response = (
        supabase.table("participants")
        .insert(
            {
                "display_name": display_name,
                "private_token": token,
                "token_hash": token_hash,
                "is_active": True,
            }
        )
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def get_participant_by_token(token: str) -> dict | None:
    """
    Hittar vilken deltagare som hör till en privat token.

    När någon öppnar:
        ?token=abc123

    så hashar vi abc123 och letar efter motsvarande token_hash i databasen.
    """

    supabase = get_supabase_client()

    token_hash = hash_token(token)

    response = (
        supabase.table("participants")
        .select("id, display_name, is_active, created_at")
        .eq("token_hash", token_hash)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def update_participant_token(
    participant_id: str,
    token: str,
) -> dict | None:
    """
    Skapar/ersätter privat token för en deltagare.

    Används om en gammal testdeltagare saknar sparad private_token,
    eller om admin vill generera en ny länk.

    Viktigt:
    Om deltagaren redan hade en länk slutar den gamla länken fungera.
    """

    supabase = get_supabase_client()

    token_hash = hash_token(token)

    response = (
        supabase.table("participants")
        .update(
            {
                "private_token": token,
                "token_hash": token_hash,
            }
        )
        .eq("id", participant_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None