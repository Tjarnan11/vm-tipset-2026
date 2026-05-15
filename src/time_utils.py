# src/time_utils.py
#
# Hjälpfunktioner för att visa tider i svensk tid.
#
# Supabase/Postgres sparar timestamptz som en absolut tid.
# En match som importeras som:
#
#   2026-06-11T21:00:00+02:00
#
# kan därför komma tillbaka från databasen som:
#
#   2026-06-11T19:00:00+00:00
#
# Det är samma tidpunkt, men i UTC.
# I UI:t vill vi däremot visa svensk lokal tid.

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def format_datetime_swedish(datetime_value: str | None) -> str:
    """
    Formaterar en datetime-sträng till svensk, lättläst tid.

    Exempel:
        2026-06-11T19:00:00+00:00

    Returnerar:
        Torsdag 11 juni, 21:00
    """

    if not datetime_value:
        return "-"

    normalized_value = str(datetime_value).replace("Z", "+00:00")

    parsed_datetime = datetime.fromisoformat(normalized_value)

    if parsed_datetime.tzinfo is None:
        parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)

    swedish_datetime = parsed_datetime.astimezone(SWEDEN_TZ)

    weekday_labels = {
        0: "Måndag",
        1: "Tisdag",
        2: "Onsdag",
        3: "Torsdag",
        4: "Fredag",
        5: "Lördag",
        6: "Söndag",
    }

    month_labels = {
        1: "januari",
        2: "februari",
        3: "mars",
        4: "april",
        5: "maj",
        6: "juni",
        7: "juli",
        8: "augusti",
        9: "september",
        10: "oktober",
        11: "november",
        12: "december",
    }

    weekday = weekday_labels[swedish_datetime.weekday()]
    day = swedish_datetime.day
    month = month_labels[swedish_datetime.month]
    time_text = swedish_datetime.strftime("%H:%M")

    return f"{weekday} {day} {month}, {time_text}"