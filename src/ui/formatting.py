# src/ui/formatting.py
#
# Små formatterings- och UI-hjälpare som används på flera sidor.

import pandas as pd
import streamlit as st

from src.scoring import is_finished_match


def format_goals_pick_label(goals_pick: str | None) -> str:
    """
    Gör om databasvärdet för över/under till svensk UI-text.

    Databasen använder:
        over
        under

    UI:t visar:
        Över 2,5 mål
        Under 2,5 mål
    """

    if goals_pick == "over":
        return "Över 2,5 mål"

    if goals_pick == "under":
        return "Under 2,5 mål"

    return "-"


def format_match_result_text(match: dict) -> str:
    """
    Returnerar en kort resultattext för en match.

    Om resultat finns:
        Mexiko 3–1 Sydafrika

    Annars:
        Mexiko – Sydafrika
    """

    if is_finished_match(match):
        return (
            f"{match['home_team']} {match['home_goals']}–"
            f"{match['away_goals']} {match['away_team']}"
        )

    return f"{match['home_team']} – {match['away_team']}"


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """
    Gör om en DataFrame till CSV-bytes för st.download_button.

    Vi använder utf-8-sig för att svenska tecken ska öppnas snyggare
    i Excel på vissa datorer.
    """

    return df.to_csv(index=False).encode("utf-8-sig")


def render_check_item(
    label: str,
    passed: bool,
    success_text: str,
    warning_text: str,
) -> None:
    """
    Visar en rad i adminens launch-checklista.

    passed=True  -> grön check
    passed=False -> gul varning
    """

    if passed:
        st.success(f"✅ {label}: {success_text}")
    else:
        st.warning(f"⚠️ {label}: {warning_text}")