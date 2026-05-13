# app.py
#
# Detta är huvudfilen för Streamlit-appen.
# När vi kör:
#
#   streamlit run app.py
#
# så startar Streamlit den här filen och bygger webbsidan uppifrån och ner.

from pathlib import Path

import pandas as pd
import streamlit as st
from src.db import get_participants


# ------------------------------------------------------------
# Sidinställningar
# ------------------------------------------------------------
# st.set_page_config måste ligga tidigt i filen.
# Här sätter vi titel i webbläsarfliken, ikon och sidlayout.
#
# layout="centered" gör sidan smalare och enklare på mobil.
# Senare kan vi testa layout="wide" för admin-sidor med stora tabeller.
st.set_page_config(
    page_title="VM-tipset 2026",
    page_icon="⚽",
    layout="centered",
)


# ------------------------------------------------------------
# Sidhuvud
# ------------------------------------------------------------
# Streamlit bygger UI med Python-funktioner.
# st.title skapar en stor rubrik.
# st.caption skapar mindre hjälptext under rubriken.
st.title("⚽ VM-tipset 2026")
st.caption("Privat gruppspelstips för kompisgänget")


# ------------------------------------------------------------
# Informationsruta
# ------------------------------------------------------------
# st.info visar en blå informationsruta.
# Just nu använder vi den för att tydligt visa att detta bara är första versionen.
st.info(
    "Det här är första lokala versionen. "
    "Nästa steg blir deltagarlänkar, databas och riktiga tips."
)


# ------------------------------------------------------------
# Enkel MVP-status
# ------------------------------------------------------------
# Det här är bara en visuell checklista för oss under utvecklingen.
# disabled=True betyder att användaren inte kan ändra checkboxen.
# value=True/False bestämmer om den är ikryssad från start.
st.header("MVP-status")

st.checkbox("Streamlit kör lokalt", value=True, disabled=True)
st.checkbox("Git-repo skapat", value=True, disabled=True)
st.checkbox("Matchdata importerad", value=False, disabled=True)
st.checkbox("Deltagarlänkar fungerar", value=False, disabled=True)
st.checkbox("Tips kan sparas", value=False, disabled=True)


# ------------------------------------------------------------
# Visa exempelmatcher från CSV
# ------------------------------------------------------------
# Just nu har vi ingen databas.
# Därför läser vi en enkel CSV-fil från data/matches_template.csv.
#
# Path kommer från Python-standardbiblioteket pathlib.
# Det är ett smidigt sätt att jobba med filvägar som fungerar bra
# på både macOS, Windows och Linux.
matches_path = Path("data/matches_template.csv")

st.header("Exempelmatcher")


# ------------------------------------------------------------
# Kontrollera att filen finns och inte är tom
# ------------------------------------------------------------
# matches_path.exists()
#   -> True om filen finns
#
# matches_path.stat().st_size
#   -> filens storlek i bytes
#
# Om filen finns men är tom vill vi inte försöka läsa den med pandas,
# eftersom det skulle ge ett fel.
if matches_path.exists() and matches_path.stat().st_size > 0:
    # pd.read_csv läser CSV-filen och skapar en DataFrame.
    # En DataFrame är ungefär som en tabell i Python.
    matches = pd.read_csv(matches_path)

    # st.dataframe visar DataFrame som en interaktiv tabell i webbsidan.
    # width="stretch" gör att tabellen använder tillgänglig bredd.
    st.dataframe(matches, width="stretch")

else:
    # Om filen saknas eller är tom visar vi en varning i appen
    # i stället för att appen kraschar.
    st.warning("Ingen matchfil hittades ännu eller filen är tom.")
    st.write("Vi kommer snart lägga in en enkel CSV-mall för matcher.")

# ------------------------------------------------------------
# Databastest: deltagare från Supabase
# ------------------------------------------------------------
# Det här är bara ett utvecklingstest.
# Om detta fungerar vet vi att:
# 1. Supabase-tabellen finns
# 2. Secrets fungerar
# 3. Streamlit kan läsa från databasen

st.header("Databastest")

try:
    participants = get_participants()

    if participants:
        st.success("Koppling till Supabase fungerar ✅")
        st.write("Aktiva deltagare:")
        st.dataframe(participants, width="stretch")
    else:
        st.warning("Kopplingen fungerar, men inga aktiva deltagare hittades.")

except Exception as error:
    st.error("Kunde inte läsa från Supabase.")
    st.exception(error)