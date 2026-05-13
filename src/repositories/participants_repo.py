# src/repositories/participants_repo.py
#
# Repository betyder ungefär:
# "En plats där vi samlar databasfunktioner för en viss typ av data."
#
# Den här filen hanterar deltagare:
# - hämta deltagare
# - skapa deltagare
# - hitta deltagare via privat token

from src.auth import hash_token
from src.db import get_supabase_client


def get_active_participants() -> list[dict]:
    """
    Hämtar alla aktiva deltagare.

    Används av admin för att se vilka som finns.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("participants")
        .select("id, display_name, is_active, created_at")
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )

    return response.data


def create_participant(display_name: str, token: str) -> dict | None:
    """
    Skapar en ny deltagare.

    Vi får in den riktiga token som deltagaren ska få i sin länk.
    Men vi sparar bara hashad token i databasen.
    """

    supabase = get_supabase_client()

    token_hash = hash_token(token)

    response = (
        supabase.table("participants")
        .insert(
            {
                "display_name": display_name,
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