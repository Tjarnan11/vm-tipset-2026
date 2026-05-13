# src/db.py
#
# Den här filen ansvarar för kontakt med Supabase.
# Poängen med att ha detta i en egen fil är att app.py inte behöver
# innehålla detaljer om hur databaskopplingen skapas.

import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def get_supabase_client() -> Client:
    """
    Skapar och återanvänder en Supabase-klient.

    Streamlit kör om scriptet ofta, till exempel när användaren klickar
    på något. Därför vill vi inte skapa en ny databas-klient i onödan
    varje gång.

    @st.cache_resource säger till Streamlit:
    "Skapa detta en gång och återanvänd det."
    """

    # Här läser vi värden från .streamlit/secrets.toml
    # Lokalt finns den filen på din dator.
    # Senare, när vi deployar, lägger vi in samma värden i Streamlit Cloud.
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]

    return create_client(supabase_url, supabase_key)


def get_participants() -> list[dict]:
    """
    Hämtar aktiva deltagare från databasen.

    Returnerar en lista av dictionaries.
    Exempel:
    [
        {
            "id": "...",
            "display_name": "Testperson",
            "is_active": True,
            "created_at": "..."
        }
    ]
    """

    supabase = get_supabase_client()

    # Detta motsvarar ungefär:
    # SELECT id, display_name, is_active, created_at
    # FROM participants
    # WHERE is_active = true
    # ORDER BY created_at;
    response = (
        supabase.table("participants")
        .select("id, display_name, is_active, created_at")
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )

    return response.data