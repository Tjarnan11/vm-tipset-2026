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

def update_match_result(
    match_id: str,
    home_goals: int,
    away_goals: int,
) -> dict | None:
    """
    Sparar resultat för en match.

    När admin fyller i resultat markerar vi matchen som färdigspelad
    genom att sätta status = "finished".

    Exempel:
        home_goals = 2
        away_goals = 1
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("matches")
        .update(
            {
                "home_goals": home_goals,
                "away_goals": away_goals,
                "status": "finished",
            }
        )
        .eq("id", match_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def clear_match_result(match_id: str) -> dict | None:
    """
    Rensar resultat för en match.

    Detta är användbart om admin råkat skriva fel resultat.
    Då sätter vi målen till null och status tillbaka till "scheduled".
    """

    supabase = get_supabase_client()

    response = (
        supabase.table("matches")
        .update(
            {
                "home_goals": None,
                "away_goals": None,
                "status": "scheduled",
            }
        )
        .eq("id", match_id)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None