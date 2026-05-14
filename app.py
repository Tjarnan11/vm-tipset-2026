# app.py
#
# Huvudfilen för Streamlit-appen.
#
# Den här filen bestämmer vilken "vy" användaren ska se:
#
# 1. Adminläge:
#       http://localhost:8501?admin=1
#
# 2. Deltagarläge:
#       http://localhost:8501?token=...
#
# 3. Startsida:
#       http://localhost:8501
#
# Senare kommer vi bryta ut admin- och deltagarvyerna till egna filer
# om app.py börjar bli för stor.

from pathlib import Path

import pandas as pd
import streamlit as st

from src.repositories.predictions_repo import (
    delete_predictions_for_matches,
    get_predictions_for_participant,
    save_predictions,
)

from src.auth import build_participant_link, generate_private_token
from src.repositories.matches_repo import get_matches
from src.repositories.participants_repo import (
    create_participant,
    get_active_participants,
    get_participant_by_token,
)


# ------------------------------------------------------------
# Sidinställningar
# ------------------------------------------------------------

st.set_page_config(
    page_title="VM-tipset 2026",
    page_icon="⚽",
    layout="centered",
)


# ------------------------------------------------------------
# Hjälpfunktioner för app.py
# ------------------------------------------------------------

def get_query_param(name: str) -> str | None:
    """
    Hämtar en query-parameter från URL:en.

    Exempel:
        http://localhost:8501?token=abc123

    Då ger:
        get_query_param("token")

    värdet:
        "abc123"

    st.query_params är Streamlits sätt att läsa URL-parametrar.
    """

    value = st.query_params.get(name)

    if value is None:
        return None

    return str(value)


def check_admin_password(password: str) -> bool:
    """
    Kontrollerar adminlösenordet mot värdet i secrets.toml.

    Vi håller detta enkelt i MVP:n.
    Senare kan vi bygga riktig admininloggning om det behövs.
    """

    expected_password = st.secrets["app"]["admin_password"]
    return password == expected_password


# ------------------------------------------------------------
# Startsida
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Adminsida
# ------------------------------------------------------------

def render_admin_page() -> None:
    """
    Enkel adminvy.

    Här kan vi just nu:
    - logga in med adminlösen
    - skapa deltagare
    - se deltagarlista

    Senare lägger vi till:
    - importera matcher
    - sätta deadline
    - fylla i resultat
    """

    st.title("Admin – VM-tipset 2026")

    password = st.text_input("Adminlösenord", type="password")

    if not password:
        st.warning("Ange adminlösenord för att fortsätta.")
        return

    if not check_admin_password(password):
        st.error("Fel adminlösenord.")
        return

    st.success("Adminläge aktivt ✅")

    st.header("Lägg till deltagare")

    with st.form("create_participant_form"):
        display_name = st.text_input("Namn på deltagare")
        submitted = st.form_submit_button("Skapa deltagare")

    if submitted:
        cleaned_name = display_name.strip()

        if not cleaned_name:
            st.error("Namn får inte vara tomt.")
        else:
            token = generate_private_token()
            participant = create_participant(cleaned_name, token)

            if participant:
                base_url = st.secrets["app"]["base_url"]
                link = build_participant_link(base_url, token)

                st.success(f"Deltagare skapad: {cleaned_name}")
                st.write("Privat länk:")

                # Viktigt:
                # Detta är enda gången vi visar den riktiga token.
                # Databasen sparar bara hashad token.
                st.code(link)
                st.info(
                    "Kopiera länken nu och skicka den till deltagaren. "
                    "I MVP:n visar vi inte gamla tokenlänkar igen."
                )
            else:
                st.error("Kunde inte skapa deltagare.")

    st.header("Aktiva deltagare")

    participants = get_active_participants()

    if participants:
        st.dataframe(participants, width="stretch")
    else:
        st.info("Inga deltagare ännu.")

    st.header("Matcher i databasen")

    render_matches_table()


# ------------------------------------------------------------
# Deltagarsida
# ------------------------------------------------------------

def render_participant_page(token: str) -> None:
    """
    Visas när användaren öppnar sin privata länk.

    Just nu visar vi bara att appen känner igen deltagaren.
    Nästa pass bygger vi själva tipsformuläret här.
    """

    participant = get_participant_by_token(token)

    if participant is None:
        st.title("Ogiltig länk")
        st.error("Den här deltagarlänken verkar inte vara giltig.")
        return

    st.title("⚽ VM-tipset 2026")
    st.success(f"Välkommen, {participant['display_name']}!")

    st.info(
        "Din privata länk fungerar. "
        "Nästa steg blir att visa matcher och låta dig lägga tips."
    )

    st.header("Lägg dina tips")

    render_predictions_form(participant)


def render_matches_table() -> None:
    """
    Visar matcher från Supabase.

    Den här funktionen används både på deltagarsidan och admin-sidan.
    Just nu visar den bara matcherna.
    I nästa pass bygger vi vidare med tipsformulär.
    """

    matches = get_matches()

    if not matches:
        st.warning("Inga matcher hittades i databasen.")
        return

    # Vi gör om listan av dictionaries till en pandas DataFrame
    # eftersom Streamlit visar DataFrames snyggt som tabeller.
    matches_df = pd.DataFrame(matches)

    # Vi väljer bara de kolumner som är relevanta att visa i UI:t.
    visible_columns = [
        "match_no",
        "group_name",
        "kickoff_at",
        "home_team",
        "away_team",
        "status",
    ]

    matches_df = matches_df[visible_columns]

    # Byt till svenska kolumnnamn i gränssnittet.
    matches_df = matches_df.rename(
        columns={
            "match_no": "Match",
            "group_name": "Grupp",
            "kickoff_at": "Avspark",
            "home_team": "Hemmalag",
            "away_team": "Bortalag",
            "status": "Status",
        }
    )

    st.dataframe(matches_df, width="stretch")


def render_predictions_form(participant: dict) -> None:
    """
    Visar formulär där en deltagare kan tippa alla matcher.

    Deltagaren kan:
    - välja 1/X/2
    - välja över/under 2,5 mål
    - spara sina tips

    Just nu finns ingen deadline-låsning.
    Det lägger vi till i nästa pass.
    """

    matches = get_matches()

    if not matches:
        st.warning("Inga matcher hittades i databasen.")
        return

    participant_id = participant["id"]

    # Hämta befintliga tips från databasen.
    existing_predictions = get_predictions_for_participant(participant_id)

    # Gör om listan till en dictionary där match_id är nyckel.
    # Då kan vi snabbt hitta tidigare tips för varje match.
    predictions_by_match_id = {
        prediction["match_id"]: prediction
        for prediction in existing_predictions
    }

    total_matches = len(matches)
    completed_matches = len(existing_predictions)

    st.info(f"Du har tippat {completed_matches} av {total_matches} matcher.")

    outcome_options = ["Välj", "1", "X", "2"]

    goals_label_to_value = {
        "Välj": None,
        "Över 2,5 mål": "over",
        "Under 2,5 mål": "under",
    }

    goals_value_to_label = {
        "over": "Över 2,5 mål",
        "under": "Under 2,5 mål",
    }

    predictions_to_save = []
    match_ids_to_delete = []
    incomplete_rows = []

    with st.form("predictions_form"):
        st.subheader("Dina tips")

        for match in matches:
            match_id = match["id"]
            existing = predictions_by_match_id.get(match_id)

            st.markdown(
                f"**Match {match['match_no']} – Grupp {match['group_name']}**"
            )
            st.write(
                f"{match['home_team']} – {match['away_team']}"
            )
            st.caption(f"Avspark: {match['kickoff_at']}")

            # Förifyll 1/X/2 om deltagaren redan har tippat matchen.
            existing_outcome = existing["outcome_pick"] if existing else "Välj"

            if existing_outcome in outcome_options:
                outcome_index = outcome_options.index(existing_outcome)
            else:
                outcome_index = 0

            outcome_pick = st.selectbox(
                "1/X/2",
                options=outcome_options,
                index=outcome_index,
                key=f"outcome_{match_id}",
            )

            # Förifyll över/under om deltagaren redan har tippat matchen.
            existing_goals_value = existing["goals_pick"] if existing else None
            existing_goals_label = goals_value_to_label.get(
                existing_goals_value,
                "Välj",
            )

            goals_options = list(goals_label_to_value.keys())
            goals_index = goals_options.index(existing_goals_label)

            goals_label = st.selectbox(
                "Över/under 2,5 mål",
                options=goals_options,
                index=goals_index,
                key=f"goals_{match_id}",
            )

            goals_pick = goals_label_to_value[goals_label]

            # Lite luft mellan matcherna.
            st.divider()

            # Vi sparar bara matcher där båda valen är gjorda.
            # Om användaren bara fyllt i ett av två val flaggar vi det.
            outcome_is_filled = outcome_pick != "Välj"
            goals_is_filled = goals_pick is not None

            if outcome_is_filled and goals_is_filled:
                predictions_to_save.append(
                    {
                        "match_id": match_id,
                        "outcome_pick": outcome_pick,
                        "goals_pick": goals_pick,
                    }
                )

            elif outcome_is_filled or goals_is_filled:
                # Om bara ett av två val är ifyllt vill vi inte spara,
                # eftersom tipset då är halvklart.
                incomplete_rows.append(match["match_no"])

            else:
                # Om båda valen är "Välj" betyder det att användaren vill
                # lämna matchen otippad.
                #
                # Om det redan fanns ett sparat tips för matchen ska vi rensa det.
                if existing:
                    match_ids_to_delete.append(match_id)

        submitted = st.form_submit_button("Spara mina tips")

    if submitted:
        if incomplete_rows:
            st.error(
                "Vissa matcher har bara ett av två val ifyllda. "
                f"Kontrollera match: {', '.join(map(str, incomplete_rows))}"
            )
            return

        delete_predictions_for_matches(
            participant_id=participant_id,
            match_ids=match_ids_to_delete,
        )

        saved_predictions = save_predictions(
            participant_id=participant_id,
            predictions=predictions_to_save,
        )

        st.success(
            f"Sparade {len(saved_predictions)} tips och rensade "
            f"{len(match_ids_to_delete)} tips ✅"
        )
        st.info("Ladda om sidan för att kontrollera att tipsen ligger kvar.")


# ------------------------------------------------------------
# Tillfälligt utvecklingstest: exempelmatcher
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# App-routing
# ------------------------------------------------------------
# Här bestämmer vi vilken vy som ska visas baserat på URL:en.

admin_mode = get_query_param("admin")
token = get_query_param("token")

if admin_mode == "1":
    render_admin_page()

elif token:
    render_participant_page(token)

else:
    render_start_page()
    render_dev_match_preview()