# src/repositories/settings_repo.py
#
# Databasfunktioner för enkla appinställningar.
#
# Just nu använder vi detta för deadline.
# Senare kan vi använda samma tabell för andra inställningar.

from datetime import datetime, timezone

from src.db import get_supabase_client


GROUP_STAGE_DEADLINE_KEY = "group_stage_deadline_at"


def get_setting(key: str) -> str | None:
    """
    Hämtar ett inställningsvärde från app_settings.

    Returnerar None om inställningen inte finns.
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("app_settings")
        .select("value")
        .eq("key", key)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]["value"]


def set_setting(key: str, value: str) -> None:
    """
    Skapar eller uppdaterar en inställning.

    upsert betyder:
    - insert om raden inte finns
    - update om raden redan finns
    """

    supabase = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()

    (
        supabase.table("app_settings")
        .upsert(
            {
                "key": key,
                "value": value,
                "updated_at": now,
            }
        )
        .execute()
    )


def get_group_stage_deadline() -> str | None:
    """
    Hämtar deadline för gruppspelstipset.
    """

    return get_setting(GROUP_STAGE_DEADLINE_KEY)


def set_group_stage_deadline(deadline_iso_utc: str) -> None:
    """
    Sparar deadline för gruppspelstipset.
    """

    set_setting(GROUP_STAGE_DEADLINE_KEY, deadline_iso_utc)