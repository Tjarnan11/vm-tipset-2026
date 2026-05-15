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
from datetime import date, time

from src.time_utils import (
    format_date_swedish,
    format_datetime_swedish,
)

from src.deadline import (
    build_deadline_iso_from_swedish_time,
    format_deadline_swedish,
    is_deadline_passed,
    parse_deadline,
)

from src.repositories.settings_repo import (
    get_group_stage_deadline,
    set_group_stage_deadline,
)

from src.repositories.predictions_repo import (
    delete_predictions_for_matches,
    get_all_predictions,
    get_predictions_for_participant,
    save_predictions,
)

from src.auth import build_participant_link, generate_private_token
from src.repositories.matches_repo import (
    clear_match_result,
    get_matches,
    update_match_result,
    upsert_matches,
)

from src.repositories.participants_repo import (
    create_participant,
    get_active_participants,
    get_participant_by_token,
    update_participant_token,
)

from src.scoring import (
    build_leaderboard,
    calculate_prediction_points,
    get_goals_pick,
    get_match_outcome,
    is_finished_match,
)

from src.repositories.bonus_repo import (
    delete_bonus_prediction,
    get_all_bonus_predictions,
    get_bonus_prediction_for_participant,
    get_bonus_scorer_results,
    save_bonus_prediction,
    upsert_bonus_scorer_result,
)

from src.group_tables import build_group_tables

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

def check_admin_token(token: str | None) -> bool:
    """
    Kontrollerar admin-token från URL:en.

    Detta används för att kunna ha en privat adminlänk som överlever
    browser-refresh, eftersom st.session_state nollställs vid riktig refresh.

    Viktigt:
    Den här token ska behandlas som hemlig.
    Den får inte committas och ska inte delas med deltagare.
    """

    if not token:
        return False

    expected_token = st.secrets["app"].get("admin_token")

    if not expected_token:
        return False

    return token == expected_token

def is_admin_logged_in() -> bool:
    """
    Kontrollerar om admin redan är inloggad i den aktuella Streamlit-sessionen.

    st.session_state lever kvar medan användaren använder appen i samma session.
    Det gör att admin inte behöver skriva lösenordet igen efter varje knapptryck
    eller rerun i Streamlit.
    """

    return st.session_state.get("admin_logged_in", False)


def render_admin_login() -> bool:
    """
    Visar admininloggning om admin inte redan är inloggad.

    Admin kan bli inloggad på två sätt:
    1. Genom att skriva adminlösenord
    2. Genom en privat admin-token i URL:en

    URL-token gör att adminläge fungerar även efter browser-refresh.
    """

    if is_admin_logged_in():
        return True

    admin_token = get_query_param("admin_token")

    if check_admin_token(admin_token):
        st.session_state["admin_logged_in"] = True
        return True

    with st.form("admin_login_form"):
        password = st.text_input("Adminlösenord", type="password")
        submitted = st.form_submit_button("Logga in")

    if not submitted:
        st.warning("Logga in för att fortsätta.")
        return False

    if check_admin_password(password):
        st.session_state["admin_logged_in"] = True
        st.success("Inloggad som admin ✅")
        st.rerun()

    st.error("Fel adminlösenord.")
    return False

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

    Detta är bara en visuell hjälp för admin.
    Den ändrar ingen data.
    """

    if passed:
        st.success(f"✅ {label}: {success_text}")
    else:
        st.warning(f"⚠️ {label}: {warning_text}")

def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """
    Gör om en DataFrame till CSV-bytes för st.download_button.

    Vi använder utf-8-sig för att svenska tecken ska öppnas snyggare
    i Excel på vissa datorer.
    """

    return df.to_csv(index=False).encode("utf-8-sig")

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


def render_deadline_admin_section() -> None:
    """
    Adminsektion för att visa och ändra deadline.

    Deadline gäller hela gruppspelstipset.
    För MVP:n har vi alltså en gemensam deadline för alla matcher.
    """

    st.header("Deadline")

    current_deadline = get_group_stage_deadline()

    if current_deadline:
        st.info(
            "Nuvarande deadline: "
            f"{format_deadline_swedish(current_deadline)} svensk tid"
        )
    else:
        st.warning("Ingen deadline är satt ännu. Tips är öppna tills deadline sätts.")

    with st.form("deadline_form"):
        selected_date = st.date_input(
            "Deadline-datum",
            value=date(2026, 6, 10),
        )

        selected_time = st.time_input(
            "Deadline-tid svensk tid",
            value=time(20, 0),
        )

        submitted = st.form_submit_button("Spara deadline")

    if submitted:
        deadline_iso = build_deadline_iso_from_swedish_time(
            selected_date,
            selected_time,
        )

        set_group_stage_deadline(deadline_iso)

        st.success(
            "Deadline sparad: "
            f"{format_deadline_swedish(deadline_iso)} svensk tid"
        )

        st.info("Ladda om sidan om du vill se uppdaterad deadline högst upp.")

def render_results_admin_section() -> None:
    """
    Adminsektion för att fylla i matchresultat.

    För MVP:n sparar vi ett resultat åt gången.
    Det är lite långsammare än en stor tabell, men mycket säkrare:
    - mindre risk att råka skriva över många matcher
    - enklare att felsöka
    - enklare UI på mobil/laptop
    """

    st.header("Fyll i matchresultat")

    matches = get_matches()

    if not matches:
        st.warning("Inga matcher hittades i databasen.")
        return

    # Skapa labels som är läsbara i selectboxen.
    # Vi behåller samtidigt matchens id internt.
    match_label_by_id = {}

    for match in matches:
        result_text = ""

        if match["status"] == "finished":
            result_text = f" ({match['home_goals']}-{match['away_goals']})"

        label = (
            f"Match {match['match_no']} – "
            f"{format_datetime_swedish(match['kickoff_at'])} – "
            f"{match['home_team']} vs {match['away_team']}"
            f"{result_text}"
        )

        match_label_by_id[match["id"]] = label

    match_ids = list(match_label_by_id.keys())

    # Säkerställ att vi har en vald match sparad i session_state.
    # Detta gör att dropdownen inte hoppar tillbaka till första matchen
    # varje gång Streamlit kör om sidan.
    if (
        "admin_selected_match_id" not in st.session_state
        or st.session_state["admin_selected_match_id"] not in match_ids
    ):
        st.session_state["admin_selected_match_id"] = match_ids[0]

    selected_match_id = st.selectbox(
        "Välj match",
        options=match_ids,
        format_func=lambda match_id: match_label_by_id[match_id],
        key="admin_selected_match_id",
    )

    selected_match = next(
        match for match in matches if match["id"] == selected_match_id
    )

    st.write(
        f"**{selected_match['home_team']} – {selected_match['away_team']}**"
    )
    st.caption(
        f"Match {selected_match['match_no']} · "
        f"Grupp {selected_match['group_name']} · "
        f"Avspark: {format_datetime_swedish(selected_match['kickoff_at'])} svensk tid · "
        f"Status: {selected_match['status']}"
    )

    current_home_goals = selected_match["home_goals"]
    current_away_goals = selected_match["away_goals"]

    # number_input behöver ett startvärde.
    # Om inget resultat finns använder vi 0 som UI-startvärde,
    # men inget sparas förrän admin aktivt trycker på knappen.
    home_goals = st.number_input(
        f"Mål för {selected_match['home_team']}",
        min_value=0,
        step=1,
        value=int(current_home_goals) if current_home_goals is not None else 0,
        key=f"admin_home_goals_{selected_match_id}",
    )

    away_goals = st.number_input(
        f"Mål för {selected_match['away_team']}",
        min_value=0,
        step=1,
        value=int(current_away_goals) if current_away_goals is not None else 0,
        key=f"admin_away_goals_{selected_match_id}",
    )

    col1, col2 = st.columns(2)

    with col1:
        save_clicked = st.button("Spara resultat")

    with col2:
        clear_clicked = st.button("Rensa resultat")

    if save_clicked:
        updated_match = update_match_result(
            match_id=selected_match_id,
            home_goals=int(home_goals),
            away_goals=int(away_goals),
        )

        if updated_match:
            st.success(
                "Resultat sparat: "
                f"{selected_match['home_team']} {home_goals}–"
                f"{away_goals} {selected_match['away_team']}"
            )
            st.info("Ladda om sidan för att se uppdaterad status i listan.")
        else:
            st.error("Kunde inte spara resultatet.")

    if clear_clicked:
        cleared_match = clear_match_result(selected_match_id)

        if cleared_match:
            st.success("Resultatet är rensat.")
            st.info("Ladda om sidan för att se uppdaterad status i listan.")
        else:
            st.error("Kunde inte rensa resultatet.")


def render_match_import_admin_section() -> None:
    """
    Adminsektion för att importera matcher från CSV.

    CSV-formatet ska vara:
        match_no,group_name,kickoff_at,home_team,away_team

    Vi använder upsert på match_no, så samma CSV kan köras flera gånger
    utan att skapa dubbletter.
    """

    st.header("Importera matcher från CSV")

    st.info(
        "CSV-filen ska ha kolumnerna: "
        "match_no, group_name, kickoff_at, home_team, away_team"
    )

    uploaded_file = st.file_uploader(
        "Ladda upp match-CSV",
        type=["csv"],
    )

    if uploaded_file is None:
        return

    try:
        matches_df = pd.read_csv(uploaded_file)
    except Exception as error:
        st.error("Kunde inte läsa CSV-filen.")
        st.exception(error)
        return

    required_columns = [
        "match_no",
        "group_name",
        "kickoff_at",
        "home_team",
        "away_team",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in matches_df.columns
    ]

    if missing_columns:
        st.error(
            "CSV-filen saknar följande kolumner: "
            f"{', '.join(missing_columns)}"
        )
        return

    # Behåll bara kolumnerna vi faktiskt vill importera.
    matches_df = matches_df[required_columns].copy()

    # Ta bort helt tomma rader om de råkat komma med i CSV:n.
    matches_df = matches_df.dropna(how="all")

    # Enkel städning av textfält.
    text_columns = ["group_name", "kickoff_at", "home_team", "away_team"]

    for column in text_columns:
        matches_df[column] = matches_df[column].astype(str).str.strip()

    # Säkerställ att match_no är heltal.
    try:
        matches_df["match_no"] = matches_df["match_no"].astype(int)
    except Exception:
        st.error("Kolumnen match_no måste innehålla heltal.")
        return

    # Validera att inga obligatoriska värden är tomma.
    invalid_rows = matches_df[
        (matches_df["group_name"] == "")
        | (matches_df["kickoff_at"] == "")
        | (matches_df["home_team"] == "")
        | (matches_df["away_team"] == "")
    ]

    if not invalid_rows.empty:
        st.error("CSV-filen innehåller tomma obligatoriska värden.")
        st.dataframe(invalid_rows, width="stretch")
        return

    # Validera att match_no inte har dubbletter i filen.
    duplicated_match_numbers = matches_df[
        matches_df["match_no"].duplicated(keep=False)
    ]

    if not duplicated_match_numbers.empty:
        st.error("CSV-filen innehåller dubbla matchnummer.")
        st.dataframe(duplicated_match_numbers, width="stretch")
        return

    st.subheader("Förhandsgranskning")
    st.dataframe(matches_df, width="stretch", hide_index=True)

    st.caption(f"Antal matcher i filen: {len(matches_df)}")

    if len(matches_df) != 72:
        st.warning(
            "Filen innehåller inte 72 matcher. "
            "Det är okej för test, men gruppspelet ska till slut ha 72 matcher."
        )

    import_clicked = st.button("Importera/uppdatera matcher")

    if import_clicked:
        rows_to_import = []

        for row in matches_df.to_dict(orient="records"):
            rows_to_import.append(
                {
                    "match_no": int(row["match_no"]),
                    "group_name": row["group_name"],
                    "kickoff_at": row["kickoff_at"],
                    "home_team": row["home_team"],
                    "away_team": row["away_team"],
                }
            )

        imported_matches = upsert_matches(rows_to_import)

        st.success(f"Importerade/uppdaterade {len(imported_matches)} matcher ✅")
        st.info("Ladda om admin-sidan för att se uppdaterad matchlista.")


def render_leaderboard_section() -> None:
    """
    Visar poängtabellen.

    Poängen räknas dynamiskt från:
    - deltagare
    - matcher med resultat
    - sparade tips

    Vi sparar alltså inte totalpoäng i databasen.
    Det minskar risken för att poängtabellen blir fel eller inaktuell.
    """

    st.header("Poängtabell")

    participants = get_active_participants()
    matches = get_matches()
    predictions = get_all_predictions()
    bonus_predictions = get_all_bonus_predictions()
    bonus_results = get_bonus_scorer_results()

    finished_matches = [
        match for match in matches
        if (
            match.get("status") == "finished"
            and match.get("home_goals") is not None
            and match.get("away_goals") is not None
        )
    ]

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    if not finished_matches:
        st.info("Inga färdigspelade matcher med resultat ännu.")
        return

    leaderboard = build_leaderboard(
        participants=participants,
        matches=matches,
        predictions=predictions,
        bonus_predictions=bonus_predictions,
        bonus_results=bonus_results,
    )

    leaderboard_df = pd.DataFrame(leaderboard)

    visible_columns = [
        "Placering",
        "Namn",
        "Poäng",
        "Bonusspelare",
        "Bonusmål",
        "Rätt 1X2",
        "Rätt Ö/U",
        "Räknade matcher",
        "Maxpoäng just nu",
    ]

    leaderboard_df = leaderboard_df[visible_columns]

    st.dataframe(
        leaderboard_df,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Poäng: 1 poäng för rätt 1/X/2 och 1 poäng för rätt över/under 2,5 mål."
    )

def render_public_predictions_overview_section() -> None:
    """
    Visar allas tips efter deadline.

    Deltagaren kan välja en match och se:
    - varje deltagares 1/X/2-tips
    - varje deltagares över/under-tips
    - poäng på matchen om resultat finns

    Den här funktionen ska bara visas efter deadline.
    """

    st.header("Allas tips")

    participants = get_active_participants()
    matches = get_matches()
    predictions = get_all_predictions()

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    if not matches:
        st.warning("Inga matcher hittades.")
        return

    predictions_by_participant_and_match = {
        (prediction["participant_id"], prediction["match_id"]): prediction
        for prediction in predictions
    }

    match_label_by_id = {}

    for match in matches:
        result_text = ""

        if is_finished_match(match):
            result_text = f" ({match['home_goals']}–{match['away_goals']})"

        label = (
            f"Match {match['match_no']} – "
            f"{format_datetime_swedish(match['kickoff_at'])} – "
            f"{match['home_team']} vs {match['away_team']}"
            f"{result_text}"
        )

        match_label_by_id[match["id"]] = label

    selected_match_id = st.selectbox(
        "Välj match",
        options=list(match_label_by_id.keys()),
        format_func=lambda match_id: match_label_by_id[match_id],
        key="public_predictions_match_select",
    )

    selected_match = next(
        match for match in matches
        if match["id"] == selected_match_id
    )

    st.subheader(
        f"{selected_match['home_team']} – {selected_match['away_team']}"
    )

    st.caption(
        f"Match {selected_match['match_no']} · "
        f"Grupp {selected_match['group_name']} · "
        f"Avspark: {format_datetime_swedish(selected_match['kickoff_at'])} svensk tid"
    )

    if is_finished_match(selected_match):
        home_goals = int(selected_match["home_goals"])
        away_goals = int(selected_match["away_goals"])

        correct_outcome = get_match_outcome(home_goals, away_goals)
        correct_goals_pick = get_goals_pick(home_goals, away_goals)

        st.success(
            f"Resultat: {selected_match['home_team']} "
            f"{home_goals}–{away_goals} "
            f"{selected_match['away_team']}"
        )

        st.caption(
            f"Rätt rad: {correct_outcome} · "
            f"{format_goals_pick_label(correct_goals_pick)}"
        )
    else:
        st.info("Resultat är inte ifyllt ännu.")

    rows = []

    for participant in participants:
        participant_id = participant["id"]

        prediction = predictions_by_participant_and_match.get(
            (participant_id, selected_match_id)
        )

        if prediction:
            outcome_pick = prediction["outcome_pick"]
            goals_pick = format_goals_pick_label(prediction["goals_pick"])

            if is_finished_match(selected_match):
                score = calculate_prediction_points(
                    prediction=prediction,
                    match=selected_match,
                )

                points = str(score["points"])
            else:
                points = "-"
        else:
            outcome_pick = "-"
            goals_pick = "-"

            if is_finished_match(selected_match):
                points = "0"
            else:
                points = "-"

            rows.append(
                {
                    "Namn": participant["display_name"],
                    "1/X/2": outcome_pick,
                    "Över/under": goals_pick,
                    "Poäng": points,
                }
            )

    predictions_df = pd.DataFrame(rows)

    st.dataframe(
        predictions_df,
        width="stretch",
        hide_index=True,
    )

def render_rules_section() -> None:
    """
    Visar reglerna för VM-tipset.

    Den här sektionen är publik för deltagaren och kan visas både före
    och efter deadline.
    """

    deadline_value = get_group_stage_deadline()

    st.header("Regler")

    st.info(
        "Du tippar alla gruppspelsmatcher i VM 2026. "
        "För varje match gör du två val: matchens 1/X/2-resultat och "
        "om matchen går över eller under 2,5 mål."
    )

    st.subheader("Deadline")

    st.warning(
        "Du kan ändra dina tips fram till deadline. "
        "Efter deadline låses tipsen och kan inte längre ändras."
    )

    st.markdown(
        f"""
        **Nuvarande deadline:**

        `{format_deadline_swedish(deadline_value)} svensk tid`
        """
    )

    st.subheader("Vad ska du tippa?")

    st.markdown(
        """
        För varje gruppspelsmatch tippar du två saker:

        **1. 1/X/2**

        - `1` = första laget i matchen vinner
        - `X` = matchen slutar oavgjort
        - `2` = andra laget i matchen vinner

        Exempel:

        Om matchen är **Tyskland – Skottland**:

        - Tyskland vinner = `1`
        - Matchen slutar oavgjort = `X`
        - Skottland vinner = `2`

        **2. Över/under 2,5 mål**

        Detta gäller det totala antalet mål i matchen, alltså båda lagens mål tillsammans.

        - **Över 2,5 mål** = matchen får 3 mål eller fler
        - **Under 2,5 mål** = matchen får 0, 1 eller 2 mål

        Exempel:

        - 3–1 = 4 mål totalt = **Över 2,5 mål**
        - 1–0 = 1 mål totalt = **Under 2,5 mål**
        - 1–1 = 2 mål totalt = **Under 2,5 mål**
        """
    )

    st.subheader("Poäng")

    st.markdown(
        """
        Du kan få max **2 poäng per match**:

        - **1 poäng** för rätt 1/X/2
        - **1 poäng** för rätt över/under 2,5 mål

        Det betyder att du kan få poäng för över/under även om du har fel på 1/X/2, och tvärtom.

        Eftersom gruppspelet har **72 matcher** finns det totalt:

        **72 × 2 = 144 möjliga poäng**
        """
    )

    st.subheader("Exempel på poäng")

    st.markdown(
        """
        Om matchen **Tyskland – Skottland** slutar **2–1** är rätt rad:

        - 1/X/2: `1`
        - Över/under: **Över 2,5 mål**

        Exempel på poäng:

        - Du tippade `1` + **Över 2,5 mål** → **2 poäng**
        - Du tippade `X` + **Över 2,5 mål** → **1 poäng**
        - Du tippade `1` + **Under 2,5 mål** → **1 poäng**
        - Du tippade `2` + **Under 2,5 mål** → **0 poäng**
        """
    )

    st.subheader("Efter deadline")

    st.markdown(
        """
        När deadline har passerat:

        - dina tips låses
        - poängtabellen visas
        - allas tips blir synliga
        - du kan se resultat och poäng per match
        - admin kan börja fylla i matchresultat
        """
    )

    st.subheader("Utslagsfråga")

    st.markdown(
        """
        Som utslagsfråga väljer du en spelare som du tror gör flest mål i gruppspelet.

        Utslagsfrågan ger inga extra poäng.

        Den används bara om flera deltagare hamnar på samma totalpoäng.
        Då hamnar den deltagare vars valda spelare gjort flest gruppspelsmål före.
        """
    )

    st.subheader("Poängtabell och sortering")

    st.markdown(
        """
        Poängtabellen sorteras så här:

        1. Totalpoäng
        2. Flest mål av vald utslagsfråga-spelare
        3. Flest rätt 1/X/2
        4. Delad placering om deltagarna fortfarande är lika

        Om deltagare fortfarande är lika efter dessa steg får de samma placering.
        """
    )

    st.subheader("Prispott")

    st.markdown(
        """
        Om tävlingen spelas med insats gäller följande princip:

        - Om en deltagare är ensam 1:a får vinnaren prispotten minus en insats.
        - Den som är ensam 2:a får tillbaka en insats.
        - Om flera deltagare delar 1:a plats delar de på hela prispotten.
        - Om en deltagare är ensam 1:a men flera deltagare delar 2:a plats, delar 2:orna på en insats.

        Exempel:

        Om 10 deltagare betalar 100 kr var är prispotten 1000 kr.

        - Ensam 1:a och ensam 2:a
            - 1:a får 900 kr
            - 2:a får 100 kr
            

        - Två deltagare delar 1:a
            -  de delar på hela prispotten, 500 kr var
            - ingen separat 2:a-pris delas ut


        - Ensam 1:a och två deltagare delar 2:a
            - 1:a får 900 kr
            - 2:orna får 50 kr var
        """
    )

    st.subheader("Admin och rättvisa")

    st.markdown(
        """
        Admin sköter deltagare, deadline och resultat.

        Appen är byggd så att deltagarnas tips inte visas för andra deltagare före deadline.
        Export av alla tips är också låst fram till deadline.

        Efter deadline kan alla deltagare se varandras tips.
        """
    )

def render_participant_status_admin_section() -> None:
    """
    Visar status för deltagarnas tips.

    Admin kan använda detta för att se:
    - vilka deltagare som har börjat tippa
    - vilka som har tippat alla matcher
    - hur många matcher som saknas per deltagare
    - när deltagaren senast sparade sina tips
    """

    st.header("Deltagarstatus")

    bonus_predictions = get_all_bonus_predictions()

    bonus_participant_ids = {
        bonus_prediction["participant_id"]
        for bonus_prediction in bonus_predictions
    }

    participants = get_active_participants()
    matches = get_matches()
    predictions = get_all_predictions()

    total_matches = len(matches)

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    if total_matches == 0:
        st.warning("Inga matcher finns i databasen ännu.")
        return

    # Samla sparade tips per deltagare.
    predicted_match_ids_by_participant = {}
    latest_update_by_participant = {}

    for prediction in predictions:
        participant_id = prediction["participant_id"]
        match_id = prediction["match_id"]

        if participant_id not in predicted_match_ids_by_participant:
            predicted_match_ids_by_participant[participant_id] = set()

        predicted_match_ids_by_participant[participant_id].add(match_id)

        updated_at = prediction.get("updated_at")

        if updated_at:
            current_latest = latest_update_by_participant.get(participant_id)

            if current_latest is None or updated_at > current_latest:
                latest_update_by_participant[participant_id] = updated_at

    rows = []

    for participant in participants:
        participant_id = participant["id"]
        predicted_match_ids = predicted_match_ids_by_participant.get(
            participant_id,
            set(),
        )

        completed_count = len(predicted_match_ids)
        remaining_count = total_matches - completed_count
        is_complete = completed_count == total_matches

        latest_update = latest_update_by_participant.get(participant_id)

        rows.append(
            {
                "Namn": participant["display_name"],
                "Status": "Klar ✅" if is_complete else "Ej klar",
                "Tippade matcher": completed_count,
                "Saknar": remaining_count,
                "Totalt": total_matches,
                "Senast uppdaterad": (
                    format_datetime_swedish(latest_update)
                    if latest_update
                    else "-"
                ),
                "Utslagsfråga": (
                    "Ifylld ✅"
                    if participant_id in bonus_participant_ids
                    else "Saknas"
                ),
            }
        )

    completed_participants = sum(
        1 for row in rows
        if row["Status"] == "Klar ✅"
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Deltagare", len(participants))

    with col2:
        st.metric("Klara", completed_participants)

    with col3:
        st.metric("Matcher", total_matches)

    status_df = pd.DataFrame(rows)

    # Visa de som inte är klara överst.
    status_df = status_df.sort_values(
        by=["Saknar", "Namn"],
        ascending=[False, True],
    )

    st.dataframe(
        status_df,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "En deltagare räknas som klar när alla matcher har både 1/X/2 "
        "och över/under 2,5 mål sparade."
    )

def render_participant_links_admin_section() -> None:
    """
    Visar deltagare och deras privata länkar.

    Detta är adminens huvudvy inför utskick:
    - se alla deltagare
    - kopiera privata länkar
    - exportera deltagarlänkar som CSV
    - generera ny länk för deltagare som saknar sparad token
    """

    st.header("Deltagarlänkar")

    participants = get_active_participants()

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    base_url = st.secrets["app"]["base_url"]

    rows = []

    for participant in participants:
        private_token = participant.get("private_token")

        private_link = (
            build_participant_link(base_url, private_token)
            if private_token
            else ""
        )

        rows.append(
            {
                "Namn": participant["display_name"],
                "Privat länk": private_link,
                "Har sparad länk": "Ja" if private_token else "Nej",
            }
        )

    links_df = pd.DataFrame(rows)

    st.dataframe(
        links_df,
        width="stretch",
        hide_index=True,
    )

    csv_data = links_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Ladda ner deltagarlänkar som CSV",
        data=csv_data,
        file_name="vm_tipset_2026_deltagarlankar.csv",
        mime="text/csv",
    )

    st.subheader("Återskapa länk")

    st.warning(
        "Detta används främst för gamla testdeltagare som saknar sparad länk. "
        "Om deltagaren redan har en fungerande länk kommer den gamla länken "
        "sluta fungera när du genererar en ny."
    )

    participant_options = {
        participant["id"]: participant["display_name"]
        for participant in participants
    }

    selected_participant_id = st.selectbox(
        "Välj deltagare",
        options=list(participant_options.keys()),
        format_func=lambda participant_id: participant_options[participant_id],
        key="regenerate_participant_link_select",
    )

    if st.button("Generera ny privat länk för vald deltagare"):
        new_token = generate_private_token()

        updated_participant = update_participant_token(
            participant_id=selected_participant_id,
            token=new_token,
        )

        if updated_participant:
            new_link = build_participant_link(base_url, new_token)

            st.success("Ny privat länk skapad.")
            st.code(new_link)
            st.info("Ladda om sidan för att se länken i tabellen ovan.")
        else:
            st.error("Kunde inte generera ny länk.")


# ------------------------------------------------------------
# Adminsida
# ------------------------------------------------------------

def render_admin_overview_section() -> None:
    """
    Visar en enkel adminöversikt.

    Syftet är att snabbt se:
    - hur många deltagare som finns
    - hur många matcher som finns
    - hur många matcher som har resultat
    - hur många deltagare som är klara med alla tips
    """

    st.header("Adminöversikt")

    participants = get_active_participants()
    matches = get_matches()
    predictions = get_all_predictions()
    deadline_value = get_group_stage_deadline()

    total_participants = len(participants)
    total_matches = len(matches)

    finished_matches = [
        match for match in matches
        if is_finished_match(match)
    ]

    predicted_match_ids_by_participant = {}

    for prediction in predictions:
        participant_id = prediction["participant_id"]
        match_id = prediction["match_id"]

        if participant_id not in predicted_match_ids_by_participant:
            predicted_match_ids_by_participant[participant_id] = set()

        predicted_match_ids_by_participant[participant_id].add(match_id)

    completed_participants = 0

    for participant in participants:
        participant_id = participant["id"]
        predicted_match_ids = predicted_match_ids_by_participant.get(
            participant_id,
            set(),
        )

        if total_matches > 0 and len(predicted_match_ids) == total_matches:
            completed_participants += 1

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Deltagare", total_participants)
        st.metric("Matcher", total_matches)

    with col2:
        st.metric("Klara deltagare", completed_participants)
        st.metric("Matcher med resultat", len(finished_matches))

    st.info(
        "Deadline: "
        f"{format_deadline_swedish(deadline_value)} svensk tid"
    )

def render_launch_checklist_section() -> None:
    """
    Visar en icke-destruktiv checklista inför launch.

    Syftet är att snabbt se om appen verkar redo att skickas till riktiga
    deltagare. Den här funktionen rensar eller ändrar ingen data.
    """

    st.header("Launch-checklista")

    participants = get_active_participants()
    matches = get_matches()
    deadline_value = get_group_stage_deadline()

    total_matches = len(matches)

    finished_matches = [
        match for match in matches
        if is_finished_match(match)
    ]

    participants_without_link = [
        participant for participant in participants
        if not participant.get("private_token")
    ]

    base_url = st.secrets["app"].get("base_url", "")

    deadline = parse_deadline(deadline_value)
    deadline_is_set = deadline is not None
    deadline_has_passed = is_deadline_passed(deadline_value)

    render_check_item(
        label="Matcher",
        passed=total_matches == 72,
        success_text="72 matcher finns i databasen.",
        warning_text=f"{total_matches} matcher finns i databasen. Gruppspelet bör ha 72.",
    )

    render_check_item(
        label="Deadline",
        passed=deadline_is_set,
        success_text=f"Deadline är satt till {format_deadline_swedish(deadline_value)} svensk tid.",
        warning_text="Ingen deadline är satt.",
    )

    if deadline_is_set:
        render_check_item(
            label="Deadline i framtiden",
            passed=not deadline_has_passed,
            success_text="Deadline ligger i framtiden.",
            warning_text="Deadline har redan passerat. Tips är låsta.",
        )

    render_check_item(
        label="Deltagarlänkar",
        passed=len(participants_without_link) == 0,
        success_text="Alla aktiva deltagare har sparad privat länk.",
        warning_text=f"{len(participants_without_link)} aktiv(a) deltagare saknar sparad länk.",
    )

    render_check_item(
        label="Base URL",
        passed=bool(base_url) and "localhost" not in base_url,
        success_text=f"Base URL ser ut att vara deployad: {base_url}",
        warning_text=f"Base URL verkar vara lokal eller saknas: {base_url}",
    )

    render_check_item(
        label="Testresultat",
        passed=len(finished_matches) == 0,
        success_text="Inga matchresultat är ifyllda.",
        warning_text=f"{len(finished_matches)} match(er) har resultat. Rensa testresultat inför riktig launch.",
    )

    if participants:
        st.info(
            f"Det finns {len(participants)} aktiv(a) deltagare. "
            "Inför riktig launch bör detta motsvara de personer du faktiskt vill bjuda in."
        )
    else:
        st.info("Det finns inga aktiva deltagare ännu.")

def render_bonus_admin_section() -> None:
    """
    Adminsektion för utslagsfrågan.

    Före deadline visas bara hur många som svarat.
    Efter deadline visas valda spelare och admin kan fylla i antal gruppspelsmål.
    """

    st.header("Utslagsfråga")

    deadline_value = get_group_stage_deadline()
    predictions_locked = is_deadline_passed(deadline_value)

    participants = get_active_participants()
    bonus_predictions = get_all_bonus_predictions()
    bonus_results = get_bonus_scorer_results()

    answered_participant_ids = {
        bonus_prediction["participant_id"]
        for bonus_prediction in bonus_predictions
    }

    st.metric(
        "Svar på utslagsfrågan",
        f"{len(answered_participant_ids)}/{len(participants)}",
    )

    if not predictions_locked:
        st.info(
            "Valda spelare visas först efter deadline. "
            "Detta är för att admin inte ska se deltagarnas val i förväg."
        )
        return

    if not bonus_predictions:
        st.warning("Inga bonusval finns ännu.")
        return

    goals_by_scorer = {
        bonus_result["scorer_name"]: int(bonus_result["goals"])
        for bonus_result in bonus_results
    }

    pick_count_by_scorer = {}

    for bonus_prediction in bonus_predictions:
        scorer_name = bonus_prediction["scorer_name"]

        if scorer_name not in pick_count_by_scorer:
            pick_count_by_scorer[scorer_name] = 0

        pick_count_by_scorer[scorer_name] += 1

    rows = []

    for scorer_name, pick_count in pick_count_by_scorer.items():
        rows.append(
            {
                "Spelare": scorer_name,
                "Antal val": pick_count,
                "Gruppspelsmål": goals_by_scorer.get(scorer_name, 0),
            }
        )

    bonus_df = pd.DataFrame(rows).sort_values(
        by=["Gruppspelsmål", "Antal val", "Spelare"],
        ascending=[False, False, True],
    )

    st.subheader("Valda spelare")

    st.dataframe(
        bonus_df,
        width="stretch",
        hide_index=True,
    )

    st.subheader("Uppdatera gruppspelsmål")

    scorer_options = sorted(pick_count_by_scorer.keys())

    selected_scorer = st.selectbox(
        "Välj spelare",
        options=scorer_options,
        key="bonus_scorer_select",
    )

    current_goals = goals_by_scorer.get(selected_scorer, 0)

    goals = st.number_input(
        "Antal mål i gruppspelet",
        min_value=0,
        step=1,
        value=current_goals,
        key="bonus_scorer_goals",
    )

    if st.button("Spara bonusmål"):
        upsert_bonus_scorer_result(
            scorer_name=selected_scorer,
            goals=int(goals),
        )

        st.success(f"Sparade {int(goals)} mål för {selected_scorer}.")
        st.info("Uppdatera sidan för att se ändringen i poängtabellen.")

def render_create_participant_admin_section() -> None:
    """
    Adminsektion för att skapa nya deltagare.

    När en deltagare skapas genereras en privat token.
    Token sparas i databasen så att admin kan visa länken igen senare.
    """

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
                st.code(link)

                st.info(
                    "Länken är också sparad i adminlistan, "
                    "så du kan kopiera den igen senare."
                )
            else:
                st.error("Kunde inte skapa deltagare.")

def render_admin_page() -> None:
    """
    Adminvy för VM-tipset.

    Adminsidan är uppdelad i flikar för att undvika en lång sida:
    - Översikt
    - Deltagare & länkar
    - Matcher
    - Resultat
    - Poängtabell
    """

    st.title("Admin – VM-tipset 2026")

    if not render_admin_login():
        return

    st.success("Adminläge aktivt ✅")

    if st.button("Logga ut från admin"):
        st.session_state["admin_logged_in"] = False
        st.rerun()

    (
        tab_overview,
        tab_participants,
        tab_matches,
        tab_results,
        tab_bonus,
        tab_leaderboard,
        tab_export,
    ) = st.tabs(
        [
            "🏠 Översikt",
            "👥 Deltagare & länkar",
            "📅 Matcher",
            "✍️ Resultat",
            "🎯 Bonus",
            "📊 Poängtabell",
            "⬇️ Export",
        ]
    )

    with tab_overview:
        render_admin_overview_section()
        render_launch_checklist_section()
        render_deadline_admin_section()

    with tab_participants:
        render_create_participant_admin_section()
        render_participant_status_admin_section()
        render_participant_links_admin_section()

    with tab_matches:
        render_match_import_admin_section()

        render_group_tables_section()

        st.header("Matcher i databasen")
        render_matches_table()

    with tab_results:
        render_results_admin_section()

    with tab_bonus:
        render_bonus_admin_section()

    with tab_leaderboard:
        render_leaderboard_section()

    with tab_export:
        render_admin_export_section()

def render_admin_export_section() -> None:
    """
    Adminsektion för att exportera viktig tävlingsdata.

    Exporterna är användbara som backup och för kontroll i Excel/Google Sheets.
    """

    st.header("Export / backup")

    participants = get_active_participants()
    matches = get_matches()
    predictions = get_all_predictions()

    deadline_value = get_group_stage_deadline()
    predictions_locked = is_deadline_passed(deadline_value)

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    if not matches:
        st.warning("Inga matcher finns i databasen.")
        return

    # ------------------------------------------------------------
    # Export 1: Poängtabell
    # ------------------------------------------------------------

    leaderboard = build_leaderboard(
        participants=participants,
        matches=matches,
        predictions=predictions,
    )

    leaderboard_df = pd.DataFrame(leaderboard)

    if not leaderboard_df.empty:
        leaderboard_columns = [
            "Placering",
            "Namn",
            "Poäng",
            "Rätt 1X2",
            "Rätt Ö/U",
            "Räknade matcher",
            "Maxpoäng just nu",
        ]

        leaderboard_df = leaderboard_df[leaderboard_columns]

        st.subheader("Poängtabell")

        st.download_button(
            label="Ladda ner poängtabell CSV",
            data=dataframe_to_csv_bytes(leaderboard_df),
            file_name="vm_tipset_2026_poangtabell.csv",
            mime="text/csv",
        )
    else:
        st.info("Poängtabell kan inte exporteras ännu.")

    # ------------------------------------------------------------
    # Export 2: Matcher och resultat
    # ------------------------------------------------------------

    matches_rows = []

    for match in matches:
        matches_rows.append(
            {
                "Match": match["match_no"],
                "Grupp": match["group_name"],
                "Avspark": format_datetime_swedish(match["kickoff_at"]),
                "Hemmalag": match["home_team"],
                "Bortalag": match["away_team"],
                "Hem": match["home_goals"],
                "Borta": match["away_goals"],
                "Status": match["status"],
            }
        )

    matches_df = pd.DataFrame(matches_rows)

    st.subheader("Matcher och resultat")

    st.download_button(
        label="Ladda ner matcher/resultat CSV",
        data=dataframe_to_csv_bytes(matches_df),
        file_name="vm_tipset_2026_matcher_resultat.csv",
        mime="text/csv",
    )

    # ------------------------------------------------------------
    # Export 3: Alla tips i långformat
    # ------------------------------------------------------------

    st.subheader("Alla tips")

    if not predictions_locked:
        st.warning(
            "Alla tips kan exporteras först efter deadline. "
            "Detta är för att admin inte ska råka se deltagarnas tips i förväg."
        )
    else:
        participant_name_by_id = {
            participant["id"]: participant["display_name"]
            for participant in participants
        }

        match_by_id = {
            match["id"]: match
            for match in matches
        }

        prediction_rows = []

        for prediction in predictions:
            participant_id = prediction["participant_id"]
            match_id = prediction["match_id"]

            participant_name = participant_name_by_id.get(
                participant_id,
                "Okänd deltagare",
            )

            match = match_by_id.get(match_id)

            if match is None:
                continue

            prediction_rows.append(
                {
                    "Deltagare": participant_name,
                    "Match": match["match_no"],
                    "Grupp": match["group_name"],
                    "Avspark": format_datetime_swedish(match["kickoff_at"]),
                    "Hemmalag": match["home_team"],
                    "Bortalag": match["away_team"],
                    "Tips 1X2": prediction["outcome_pick"],
                    "Tips över/under": format_goals_pick_label(
                        prediction["goals_pick"]
                    ),
                    "Senast uppdaterad": format_datetime_swedish(
                        prediction.get("updated_at")
                    ),
                }
            )

        predictions_df = pd.DataFrame(prediction_rows)

        if predictions_df.empty:
            st.info("Inga tips finns att exportera ännu.")
        else:
            predictions_df = predictions_df.sort_values(
                by=["Deltagare", "Match"],
                ascending=[True, True],
            )

            st.download_button(
                label="Ladda ner alla tips CSV",
                data=dataframe_to_csv_bytes(predictions_df),
                file_name="vm_tipset_2026_alla_tips.csv",
                mime="text/csv",
            )
    # ------------------------------------------------------------
    # Export 4: Deltagarstatus
    # ------------------------------------------------------------

    total_matches = len(matches)

    predicted_match_ids_by_participant = {}

    for prediction in predictions:
        participant_id = prediction["participant_id"]
        match_id = prediction["match_id"]

        if participant_id not in predicted_match_ids_by_participant:
            predicted_match_ids_by_participant[participant_id] = set()

        predicted_match_ids_by_participant[participant_id].add(match_id)

    status_rows = []

    for participant in participants:
        participant_id = participant["id"]
        predicted_match_ids = predicted_match_ids_by_participant.get(
            participant_id,
            set(),
        )

        completed_count = len(predicted_match_ids)

        status_rows.append(
            {
                "Namn": participant["display_name"],
                "Tippade matcher": completed_count,
                "Saknar": total_matches - completed_count,
                "Totalt": total_matches,
                "Klar": "Ja" if completed_count == total_matches else "Nej",
            }
        )

    status_df = pd.DataFrame(status_rows)

    st.subheader("Deltagarstatus")

    st.download_button(
        label="Ladda ner deltagarstatus CSV",
        data=dataframe_to_csv_bytes(status_df),
        file_name="vm_tipset_2026_deltagarstatus.csv",
        mime="text/csv",
    )


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

    deadline_value = get_group_stage_deadline()
    predictions_locked = is_deadline_passed(deadline_value)

    tab_tips, tab_leaderboard, tab_predictions, tab_matches, tab_rules = st.tabs(
        [
            "📝 Mina tips",
            "📊 Poängtabell",
            "🧾 Allas tips",
            "📅 Matcher & resultat",
            "ℹ️ Regler",
        ]
    )

    with tab_tips:
        st.info(
            "Deadline: "
            f"{format_deadline_swedish(deadline_value)} svensk tid"
        )

        render_bonus_prediction_section(
            participant=participant,
            predictions_locked=predictions_locked,
        )

        st.divider()

        render_predictions_form(
            participant=participant,
            predictions_locked=predictions_locked,
        )

    with tab_leaderboard:
        if predictions_locked:
            render_leaderboard_section()
        else:
            st.info("Poängtabellen visas efter deadline.")

    with tab_predictions:
        if predictions_locked:
            render_public_predictions_overview_section()
        else:
            st.info("Allas tips visas efter deadline.")

    with tab_matches:
        render_public_matches_results_section(
            predictions_locked=predictions_locked,
        )

    with tab_rules:
        render_rules_section()


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
        "home_goals",
        "away_goals",
        "status",
    ]

    matches_df = matches_df[visible_columns]

    # Supabase returnerar ofta timestamptz i UTC.
    # Vi visar avspark i svensk tid i UI:t.
    matches_df["kickoff_at"] = matches_df["kickoff_at"].apply(
        format_datetime_swedish
    )

    # Byt till svenska kolumnnamn i gränssnittet.
    matches_df = matches_df.rename(
        columns={
            "match_no": "Match",
            "group_name": "Grupp",
            "kickoff_at": "Avspark",
            "home_team": "Hemmalag",
            "away_team": "Bortalag",
            "home_goals": "Hem",
            "away_goals": "Borta",
            "status": "Status",
        }
    )

    st.dataframe(matches_df, width="stretch")

def render_public_matches_results_section(
    predictions_locked: bool,
) -> None:
    """
    Visar matcher, resultat och gruppställningar.

    Detta är en översiktssida för deltagaren:
    - gruppställningar
    - schema/resultat
    """

    tab_groups, tab_matches = st.tabs(
        [
            "🏆 Grupper",
            "📅 Matcher",
        ]
    )

    with tab_groups:
        render_group_tables_section()

    with tab_matches:
        st.header("Matcher & resultat")

        matches = get_matches()

        if not matches:
            st.warning("Inga matcher hittades i databasen.")
            return
        
        participants = get_active_participants() if predictions_locked else []
        predictions = get_all_predictions() if predictions_locked else []

        predictions_by_participant_and_match = {
            (prediction["participant_id"], prediction["match_id"]): prediction
            for prediction in predictions
        }

        last_date_heading = None

        for match in matches:
            date_heading = format_date_swedish(match["kickoff_at"])

            if date_heading != last_date_heading:
                st.markdown(f"### {date_heading}")
                last_date_heading = date_heading

            with st.container(border=True):
                st.markdown(
                    f"**Match {match['match_no']} · Grupp {match['group_name']}**"
                )

                st.markdown(
                    f"### {match['home_team']} – {match['away_team']}"
                )

                st.caption(
                    f"Avspark: {format_datetime_swedish(match['kickoff_at'])} svensk tid"
                )

                if is_finished_match(match):
                    st.success(
                        f"Resultat: {match['home_team']} "
                        f"{match['home_goals']}–{match['away_goals']} "
                        f"{match['away_team']}"
                    )

                    if predictions_locked:
                        rows = []

                        for participant in participants:
                            participant_id = participant["id"]

                            prediction = predictions_by_participant_and_match.get(
                                (participant_id, match["id"])
                            )

                            if prediction:
                                score = calculate_prediction_points(
                                    prediction=prediction,
                                    match=match,
                                )

                                outcome_pick = prediction["outcome_pick"]
                                goals_pick = format_goals_pick_label(
                                    prediction["goals_pick"]
                                )
                                points = score["points"]
                            else:
                                outcome_pick = "-"
                                goals_pick = "-"
                                points = 0

                            rows.append(
                                {
                                    "Namn": participant["display_name"],
                                    "1/X/2": outcome_pick,
                                    "Över/under": goals_pick,
                                    "Poäng": points,
                                }
                            )

                        points_df = pd.DataFrame(rows)

                        points_df = points_df.sort_values(
                            by=["Poäng", "Namn"],
                            ascending=[False, True],
                        )

                        with st.expander("Tips och poäng på denna match"):
                            st.dataframe(
                                points_df,
                                width="stretch",
                                hide_index=True,
                            )

                else:
                    st.info("Resultat: ej ifyllt ännu")

                    if predictions_locked:
                        rows = []

                        for participant in participants:
                            participant_id = participant["id"]

                            prediction = predictions_by_participant_and_match.get(
                                (participant_id, match["id"])
                            )

                            if prediction:
                                outcome_pick = prediction["outcome_pick"]
                                goals_pick = format_goals_pick_label(
                                    prediction["goals_pick"]
                                )
                            else:
                                outcome_pick = "-"
                                goals_pick = "-"

                            rows.append(
                                {
                                    "Namn": participant["display_name"],
                                    "1/X/2": outcome_pick,
                                    "Över/under": goals_pick,
                                }
                            )

                        tips_df = pd.DataFrame(rows)

                        with st.expander("Tips på denna match"):
                            st.dataframe(
                                tips_df,
                                width="stretch",
                                hide_index=True,
                            )

def render_group_tables_section() -> None:
    """
    Visar gruppställningar baserat på inmatade resultat.

    Tabellen uppdateras automatiskt när admin fyller i matchresultat.
    """

    st.header("Grupper")

    matches = get_matches()

    if not matches:
        st.warning("Inga matcher hittades i databasen.")
        return

    group_tables = build_group_tables(matches)

    if not group_tables:
        st.info("Inga grupper hittades.")
        return

    for group_name, rows in group_tables.items():
        st.subheader(f"Grupp {group_name}")

        group_df = pd.DataFrame(rows)

        visible_columns = [
            "Lag",
            "M",
            "V",
            "O",
            "F",
            "GM",
            "IM",
            "MS",
            "P",
        ]

        group_df = group_df[visible_columns]

        st.dataframe(
            group_df,
            width="stretch",
            hide_index=True,
        )

    st.caption(
        "Tabellen sorteras efter poäng, målskillnad, gjorda mål och lagnamn. "
        "Fullständig officiell tiebreaker-logik kan läggas till senare."
    )

def render_bonus_prediction_section(
    participant: dict,
    predictions_locked: bool,
) -> None:
    """
    Visar och sparar deltagarens svar på utslagsfrågan.

    Utslagsfrågan används bara vid lika totalpoäng.
    Den ger alltså inte extra poäng i grundpoängen.
    """

    st.subheader("Utslagsfråga")

    st.info(
        "Vem tror du gör flest mål i gruppspelet? "
        "Detta används bara som utslagsfråga om flera deltagare får samma poäng."
    )

    participant_id = participant["id"]
    existing_bonus = get_bonus_prediction_for_participant(participant_id)

    existing_scorer_name = (
        existing_bonus["scorer_name"]
        if existing_bonus
        else ""
    )

    if predictions_locked:
        if existing_scorer_name:
            st.success(f"Ditt val: {existing_scorer_name}")
        else:
            st.warning("Du har inget sparat svar på utslagsfrågan.")

        st.caption("Utslagsfrågan är låst eftersom deadline har passerat.")
        return

    with st.form("bonus_prediction_form"):
        scorer_name = st.text_input(
            "Spelare",
            value=existing_scorer_name,
            placeholder="Exempel: Kylian Mbappé",
        )

        submitted = st.form_submit_button("Spara utslagsfråga")

    if submitted:
        cleaned_name = scorer_name.strip()

        if cleaned_name:
            save_bonus_prediction(
                participant_id=participant_id,
                scorer_name=cleaned_name,
            )

            st.toast("Utslagsfrågan är sparad ✅", icon="✅")
            st.success(f"Sparat val: {cleaned_name}")
        else:
            delete_bonus_prediction(participant_id)
            st.toast("Utslagsfrågan är rensad", icon="🧹")
            st.info("Utslagsfrågan är rensad.")

def render_predictions_form(
    participant: dict,
    predictions_locked: bool,
) -> None:
    """
    Visar formulär där en deltagare kan tippa alla matcher.

    Deltagaren kan:
    - välja 1/X/2
    - välja över/under 2,5 mål
    - spara sina tips

    Formuläret låses om deadline har passerat.
    Efter deadline visas även resultat och poäng per match.
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

    completion_ratio = (
        completed_matches / total_matches
        if total_matches > 0
        else 0
    )

    st.subheader("Din status")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Tippade matcher", f"{completed_matches}/{total_matches}")

    with col2:
        st.metric("Saknas", total_matches - completed_matches)

    st.progress(completion_ratio)

    if predictions_locked:
        st.error("Deadline har passerat. Dina tips är låsta.")
    else:
        st.success("Tipsen är öppna. Du kan ändra fram till deadline.")

    st.caption(
        "För varje match tippar du både 1/X/2 och över/under 2,5 mål."
    )

    view_filter = st.radio(
        "Visa matcher",
        options=["Alla matcher", "Endast otippade"],
        horizontal=True,
    )

    if view_filter == "Endast otippade":
        matches_to_render = [
            match for match in matches
            if match["id"] not in predictions_by_match_id
        ]
    else:
        matches_to_render = matches

    if not matches_to_render:
        st.success("Alla matcher i detta filter är tippade ✅")
        return

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

    with st.form("predictions_form", border=False):
        st.subheader("Dina tips")

        submitted_top = st.form_submit_button(
            "Spara ändringar",
            disabled=predictions_locked,
            key="save_predictions_top",
        )

        st.caption(
            "Tipsen sparas först när du trycker på Spara ändringar."
        )

        last_date_heading = None

        for match in matches_to_render:
            match_id = match["id"]
            existing = predictions_by_match_id.get(match_id)

            date_heading = format_date_swedish(match["kickoff_at"])

            if date_heading != last_date_heading:
                st.markdown(f"### {date_heading}")
                last_date_heading = date_heading

            with st.container(border=True):
                st.markdown(
                    f"**Match {match['match_no']} · Grupp {match['group_name']}**"
                )

                st.markdown(
                    f"### {match['home_team']} – {match['away_team']}"
                )

                st.caption(
                    f"Avspark: {format_datetime_swedish(match['kickoff_at'])} svensk tid"
                )

                # Efter deadline visar vi resultat och spelarens poäng per match.
                # Före deadline ska deltagaren bara fokusera på att lägga sina tips.
                if predictions_locked:
                    if is_finished_match(match):
                        home_goals = int(match["home_goals"])
                        away_goals = int(match["away_goals"])

                        correct_outcome = get_match_outcome(home_goals, away_goals)
                        correct_goals_pick = get_goals_pick(home_goals, away_goals)

                        st.markdown(
                            f"**Resultat:** "
                            f"{match['home_team']} {home_goals}–{away_goals} {match['away_team']}"
                        )

                        st.caption(
                            f"Rätt rad: {correct_outcome} · "
                            f"{format_goals_pick_label(correct_goals_pick)}"
                        )

                        if existing:
                            score = calculate_prediction_points(
                                prediction=existing,
                                match=match,
                            )

                            st.markdown(
                                f"**Din poäng på matchen:** "
                                f"{score['points']}/2 "
                                f"({score['outcome_points']}p 1X2, "
                                f"{score['goals_points']}p Ö/U)"
                            )
                        else:
                            st.markdown(
                                "**Din poäng på matchen:** 0/2 "
                                "(inget sparat tips)"
                            )
                    else:
                        st.caption("Resultat: ej spelad eller ej ifylld ännu.")

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
                    disabled=predictions_locked,
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
                    disabled=predictions_locked,
                )

                goals_pick = goals_label_to_value[goals_label]

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
                    incomplete_rows.append(match["match_no"])

                else:
                    if existing:
                        match_ids_to_delete.append(match_id)

            # Lite luft mellan korten.
            st.write("")

        submitted_bottom = st.form_submit_button(
            "Spara ändringar",
            disabled=predictions_locked,
            key="save_predictions_bottom",
        )   

    submitted = submitted_top or submitted_bottom

    if submitted:
        if predictions_locked:
            st.error("Deadline har passerat. Tipsen kan inte sparas.")
            return
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

        existing_match_ids = set(predictions_by_match_id.keys())

        saved_match_ids = {
            prediction["match_id"]
            for prediction in predictions_to_save
        }

        deleted_match_ids = set(match_ids_to_delete)

        # Räkna ut hur många matcher som är ifyllda efter sparningen.
        # Detta är bättre än len(saved_predictions), eftersom saved_predictions
        # bara gäller det som skickades till databasen i just denna sparning.
        filled_match_ids_after_save = (
            existing_match_ids
            | saved_match_ids
        ) - deleted_match_ids

        filled_count_after_save = len(filled_match_ids_after_save)
        cleared_count = len(match_ids_to_delete)

        if cleared_count > 0:
            save_message = (
                f"Dina tips är sparade ✅ "
                f"({filled_count_after_save}/{total_matches} ifyllda, "
                f"{cleared_count} rensade)"
            )
        else:
            save_message = (
                f"Dina tips är sparade ✅ "
                f"({filled_count_after_save}/{total_matches} ifyllda)"
            )

        st.toast(save_message, icon="✅")
        st.success(save_message)


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