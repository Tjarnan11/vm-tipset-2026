# src/repositories/matches_repo.py
#
# Den här filen innehåller databasfunktioner för matcher.
#
# Tanken är att app.py inte ska behöva veta exakt hur vi pratar med Supabase.
# app.py ska bara kunna säga:
#
#   matches = get_matches()
#
# och sedan få tillbaka en lista med matcher.

from src.db import get_supabase_client


def get_matches() -> list[dict]:
    """
    Hämtar alla matcher från databasen.

    Returnerar en lista av dictionaries.
    Varje dictionary motsvarar en rad i matches-tabellen.

    Exempel:
    {
        "id": "...",
        "match_no": 1,
        "group_name": "A",
        "kickoff_at": "2026-06-11T19:00:00+00:00",
        "home_team": "Lag A1",
        "away_team": "Lag A2",
        "home_goals": None,
        "away_goals": None,
        "status": "scheduled"
    }
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("matches")
        .select(
            "id, match_no, group_name, kickoff_at, "
            "home_team, away_team, home_goals, away_goals, status"
        )
        .order("match_no")
        .execute()
    )

    return response.data