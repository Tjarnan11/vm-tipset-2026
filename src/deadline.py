# src/deadline.py
#
# Hjälpfunktioner för deadline.
#
# Viktig princip:
# - I UI:t tänker vi svensk tid: Europe/Stockholm
# - I databasen sparar vi UTC-tid
#
# Det gör att tidsjämförelser blir mer robusta.

from datetime import date as Date
from datetime import datetime, time as Time, timezone
from zoneinfo import ZoneInfo


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def now_utc() -> datetime:
    """
    Returnerar aktuell tid i UTC.

    Vi använder UTC när vi jämför mot deadline eftersom databasen också
    lagrar tiden som UTC/timestamptz.
    """

    return datetime.now(timezone.utc)


def build_deadline_iso_from_swedish_time(
    deadline_date: Date,
    deadline_time: Time,
) -> str:
    """
    Tar datum och tid från admin-UI:t och gör om det till ISO-format i UTC.

    Exempel:
        2026-06-10 20:00 svensk tid

    sparas ungefär som:
        2026-06-10T18:00:00+00:00

    beroende på sommartid.
    """

    local_datetime = datetime.combine(
        deadline_date,
        deadline_time,
        tzinfo=SWEDEN_TZ,
    )

    utc_datetime = local_datetime.astimezone(timezone.utc)

    return utc_datetime.isoformat()


def parse_deadline(deadline_value: str | None) -> datetime | None:
    """
    Gör om deadline-strängen från databasen till ett datetime-objekt.

    Returnerar None om ingen deadline är satt.
    """

    if not deadline_value:
        return None

    # fromisoformat hanterar format som:
    # 2026-06-10T18:00:00+00:00
    parsed = datetime.fromisoformat(deadline_value)

    # Om tiden mot förmodan saknar timezone, tolka den som UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def is_deadline_passed(deadline_value: str | None) -> bool:
    """
    Returnerar True om deadline har passerat.

    Om ingen deadline är satt returnerar vi False.
    Det betyder att tips är öppna tills admin faktiskt sätter en deadline.
    """

    deadline = parse_deadline(deadline_value)

    if deadline is None:
        return False

    return now_utc() >= deadline


def format_deadline_swedish(deadline_value: str | None) -> str:
    """
    Formaterar deadline på ett läsbart svenskt sätt för UI:t.
    """

    deadline = parse_deadline(deadline_value)

    if deadline is None:
        return "Ingen deadline satt"

    swedish_time = deadline.astimezone(SWEDEN_TZ)

    return swedish_time.strftime("%Y-%m-%d %H:%M")