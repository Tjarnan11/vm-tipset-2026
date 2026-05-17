# src/ui/start_page.py
#
# Startsida och tillfällig utvecklingsvy.

from pathlib import Path

import pandas as pd
import streamlit as st

def render_start_page() -> None:
    """
    Visas om användaren inte har admin=1 eller token i URL:en.
    """

    st.title("⚽ VM-tipset 2026")
    st.caption("Privat gruppspelstips för kompisgänget")

    st.info(
        "Det här är en privat app. "
        "Öppna din personliga länk för att lägga tips."
    )

    st.write("Admin kan öppna adminläget med:")

    st.code("http://localhost:8501?admin=1")


def render_dev_match_preview() -> None:
    """
    Tillfällig utvecklingsvy som visar CSV-mallen.

    Den här kan vi ta bort eller flytta senare.
    """

    st.header("Utvecklingstest: exempelmatcher")

    matches_path = Path("data/matches_template.csv")

    if matches_path.exists() and matches_path.stat().st_size > 0:
        matches = pd.read_csv(matches_path)
        st.dataframe(matches, width="stretch")
    else:
        st.warning("Ingen matchfil hittades ännu eller filen är tom.")

