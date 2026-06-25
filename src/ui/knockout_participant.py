# src/ui/knockout_participant.py
#
# Deltagarvy för slutspelstipset.
#
# Visar:
# - slutspelsrundor
# - slutspelsmatcher
# - tipsformulär för öppna rundor
# - read-only-läge för låsta/stängda rundor

import pandas as pd
import streamlit as st

from src.deadline import is_deadline_passed
from src.repositories.knockout_repo import (
    get_all_knockout_predictions,
    get_knockout_matches,
    get_knockout_matches_for_round,
    get_knockout_predictions_for_participant,
    get_knockout_rounds,
    save_knockout_predictions,
    get_knockout_final_prediction_for_participant,
)
from src.time_utils import format_datetime_swedish
from src.ui.formatting import format_goals_pick_label

from src.ui.knockout_leaderboard import render_knockout_leaderboard_section

from src.ui.knockout_final import render_knockout_final_prediction_section

from src.knockout_scoring import calculate_knockout_match_points
from src.scoring import get_goals_pick, get_match_outcome

from src.repositories.participants_repo import get_active_participants


def is_knockout_round_open_for_predictions(
    knockout_round: dict,
) -> bool:
    """
    Kontrollerar om en slutspelsrunda är öppen för tips.

    Regler:
    - rundans status måste vara open
    - deadline måste finnas
    - deadline får inte ha passerat
    """

    deadline_at = knockout_round.get("deadline_at")

    if knockout_round.get("status") != "open":
        return False

    if not deadline_at:
        return False

    return not is_deadline_passed(deadline_at)

def is_finished_knockout_match(match: dict) -> bool:
    """
    Kontrollerar om en slutspelsmatch har fulltidsresultat.
    """

    return (
        match.get("status") == "finished"
        and match.get("home_goals_ft") is not None
        and match.get("away_goals_ft") is not None
    )

def is_knockout_round_locked_for_match(match: dict) -> bool:
    """
    Kontrollerar om en match tillhör en låst/stängd slutspelsrunda.

    Allas tips ska bara visas när rundan inte längre är öppen.
    """

    round_info = match.get("knockout_rounds") or {}
    status = round_info.get("status")

    return status in {
        "locked",
        "finished",
    }

def format_knockout_match_result_text(match: dict) -> str:
    """
    Returnerar kompakt matchtext.

    Om resultat finns:
        Argentina 2–1 Frankrike

    Annars:
        Argentina – Frankrike
    """

    if is_finished_knockout_match(match):
        return (
            f"{match['home_team']} {match['home_goals_ft']}–"
            f"{match['away_goals_ft']} {match['away_team']}"
        )

    return f"{match['home_team']} – {match['away_team']}"

def get_prediction_outcome_text(prediction: dict) -> str:
    """
    Härleder 1/X/2 från deltagarens exakta slutspelstips.
    """

    return get_match_outcome(
        int(prediction["predicted_home_goals"]),
        int(prediction["predicted_away_goals"]),
    )

def _get_match_round_id(match: dict) -> str | None:
    round_info = match.get("knockout_rounds") or {}
    return match.get("round_id") or round_info.get("id")


def _looks_like_knockout_placeholder(value: str | None) -> bool:
    if not value:
        return True

    text = str(value).strip().lower()

    placeholder_markers = [
        "grupp",
        "group",
        "vinnare",
        "winner",
        "förlorare",
        "loser",
        "bästa",
        "trea",
        "3:a",
        "1:a",
        "2:a",
        "match",
    ]

    return any(marker in text for marker in placeholder_markers)


def _is_actual_team_assigned(
    current_team: str | None,
    original_placeholder: str | None,
) -> bool:
    if not current_team:
        return False

    current_team_clean = str(current_team).strip()

    if not current_team_clean:
        return False

    placeholder_clean = (
        str(original_placeholder).strip()
        if original_placeholder
        else ""
    )

    if placeholder_clean and current_team_clean == placeholder_clean:
        return False

    if _looks_like_knockout_placeholder(current_team_clean):
        return False

    return True


def _count_complete_match_pairs_for_round(
    round_id: str,
    matches: list[dict],
) -> tuple[int, int]:
    """
    Returnerar antal klara matchpar och totalt antal matcher för en runda.

    Ett matchpar räknas som klart när både hemma- och bortalag är faktiska lag,
    inte placeholders.
    """

    round_matches = [
        match
        for match in matches
        if _get_match_round_id(match) == round_id
    ]

    complete_match_pairs = 0

    for match in round_matches:
        home_assigned = _is_actual_team_assigned(
            match.get("home_team"),
            match.get("home_placeholder"),
        )

        away_assigned = _is_actual_team_assigned(
            match.get("away_team"),
            match.get("away_placeholder"),
        )

        if home_assigned and away_assigned:
            complete_match_pairs += 1

    return complete_match_pairs, len(round_matches)

def render_knockout_rounds_overview() -> None:
    """
    Visar slutspelsrundor för deltagaren.
    """

    rounds = get_knockout_rounds()
    matches = get_knockout_matches()

    if not rounds:
        st.info("Slutspelet är inte förberett ännu.")
        return

    st.caption(
        "Matchpar klara visar hur många matcher i rundan som har två faktiska lag "
        "inlagda och därmed är färdiga att tippa på."
    )

    status_label_by_value = {
        "not_started": "Inte öppnad",
        "open": "Öppen",
        "locked": "Låst",
        "finished": "Avslutad",
    }

    rows = []

    sorted_rounds = sorted(
        rounds,
        key=lambda knockout_round: knockout_round.get("sort_order", 999),
    )

    for knockout_round in sorted_rounds:
        deadline_at = knockout_round.get("deadline_at")
        complete_match_pairs, total_matches = _count_complete_match_pairs_for_round(
            round_id=knockout_round["id"],
            matches=matches,
        )

        status = knockout_round.get("status", "not_started")

        rows.append(
            {
                "Runda": knockout_round["name"],
                "Matchpar klara": f"{complete_match_pairs}/{total_matches}",
                "Deadline": (
                    format_datetime_swedish(deadline_at)
                    if deadline_at
                    else "-"
                ),
                "Status": status_label_by_value.get(status, status),
            }
        )

    rounds_df = pd.DataFrame(rows)

    st.dataframe(
        rounds_df,
        width="stretch",
        hide_index=True,
    )


def render_knockout_rules_section() -> None:
    """
    Visar regler för slutspelstipset.

    Reglerna ligger inne i Slutspel-fliken eftersom slutspelet är en separat
    tävlingsdel från gruppspelet.
    """

    st.subheader("Slutspelsregler")

    st.info(
        "Slutspelstipset är separat från gruppspelstipset. "
        "Du tippar varje slutspelsrunda när den öppnas."
    )

    st.markdown(
        """
        ### Deadlines per runda

        Slutspelet har en deadline per runda.

        En runda är tippbar när:

        - rundans status är `open`
        - deadline ligger i framtiden

        När deadline har passerat låses tipsen för den rundan.

        Eftersom vissa slutspelsmatcher blir klara senare än andra kan tiden att
        tippa en specifik runda ibland bli kort. Lägg därför gärna dina tips så
        snart matcherna i en runda är kända.
        """
    )

    st.markdown(
        """
        ### Vad tippar du per match?

        För varje slutspelsmatch tippar du:

        1. exakt resultat efter ordinarie tid
        2. över/under 2,5 mål efter ordinarie tid
        3. eventuell första målskytt under ordinarie tid

        **Ordinarie tid betyder 90 minuter + tilläggstid.**

        Förlängning och straffläggning räknas inte för något av matchtipsen:
        exakt resultat, 1/X/2, över/under eller första målskytt.
        """
    )

    st.markdown(
        """
        ### Exakt resultat och 1/X/2

        I slutspelet fyller du bara i exakt resultat.

        Appen räknar automatiskt ut 1/X/2 från ditt resultat:

        - `2–1` ger `1`
        - `1–1` ger `X`
        - `0–2` ger `2`

        Du kan alltså få poäng för rätt matchutfall även om du inte har exakt
        rätt resultat.
        """
    )

    st.markdown(
        """
        ### Över/under 2,5 mål

        Över/under gäller antal mål efter fulltid:

        - **Över 2,5 mål** = minst 3 mål
        - **Under 2,5 mål** = 0, 1 eller 2 mål

        Över/under-valet är separat från ditt exakta resultat.
        """
    )

    st.markdown(
        """
        ### Första målskytt

        Du skriver själv vilken spelare du tror gör matchens första mål under ordinarie tid.

        Första målskytt gäller endast mål under 90 minuter + tilläggstid.
        Mål i förlängning eller straffläggning räknas inte.

        Eftersom detta är fritext bedömer admin manuellt om tipset är rätt eller fel.

        Du kan lämna första målskytt tomt, men då kan du inte få poäng för första målskytt på den matchen.
        """
    )

    st.markdown(
        """
        ### Poäng per slutspelsmatch

        Du kan få max **8 poäng per match**:

        - **1 poäng** för rätt 1/X/2 efter ordinarie tid
        - **1 poäng** för rätt över/under 2,5 mål efter ordinarie tid
        - **2 poäng** för exakt rätt resultat efter ordinarie tid
        - **4 poäng** för rätt första målskytt

        Om du har exakt rätt resultat får du också rätt 1/X/2.
        """
    )

    st.markdown(
        """
        ### Finaltips

        Innan slutspelet börjar tippar du också:

        - vilka två lag som går till final
        - vilket av dina två finallag som vinner VM pokalen

        Notera att i detta tips gäller såklart inte resultatet efter ordinarie tid, utan det slutliga resultatet efter eventuell förlängning och straffläggning.

        Vinnaren måste alltså vara ett av de två lag du har valt som finalister.

        Finaltipsen låses vid första slutspelsrundans deadline.

        Poäng:

        - **5 poäng** per rätt finallag
        - **10 poäng** för rätt finalvinnare

        Eftersom finaltipsen är fritext bedömer admin manuellt hur många
        finallag som var rätt och om vinnaren var rätt.
        """
    )

    st.markdown(
        """
        ### Sortering i slutspelstabellen

        Slutspelstabellen sorteras i första hand efter totalpoäng.

        Vid lika poäng används:

        1. flest exakta resultat
        2. flest rätt 1/X/2
        3. flest rätt första målskytt
        4. delad placering om deltagarna fortfarande är lika
        """
    )

    st.markdown(
        """
        ### Prispott

        Slutspelstipset räknas som en separat tävling från gruppspelstipset.

        Om slutspelet spelas med insats används samma grundprincip som i gruppspelet:

        - Om en deltagare är ensam 1:a får vinnaren prispotten minus en insats.
        - Den som är ensam 2:a får tillbaka en insats.
        - Om flera deltagare delar 1:a plats delar de på hela prispotten.
        - Om en deltagare är ensam 1:a men flera deltagare delar 2:a plats, delar 2:orna på en insats.
        """
    )

    st.markdown(
        """
        ### Admin och rättvisa

        Admin sköter rundor, deadlines, slutspelsmatcher, resultat och manuell bedömning av fritextsvar.

        Deltagarnas slutspelstips ska inte visas för andra deltagare förrän relevant rundas deadline har passerat eller rundan är låst.

        Efter att deadline har passerat eller rundan är låst kan tips och poäng för den rundan visas.
        """
    )

def render_saved_knockout_predictions_section(
    participant: dict,
) -> None:
    """
    Visar en read-only-sammanfattning av deltagarens sparade slutspelstips.

    Syftet är att deltagaren tydligt ska kunna kontrollera vad som faktiskt
    ligger sparat i databasen.
    """

    st.subheader("Sparade slutspelstips")

    st.info(
        "Här ser du de slutspelstips som faktiskt är sparade i databasen. "
        "Detta är en kontrollvy. Om du ändrar något under Tips & resultat "
        "behöver du trycka på Spara innan ändringen syns här."
    )

    st.caption(
        "När en runda är låst visas dina resultat och poäng per match under "
        "fliken Tips & resultat."
    )

    participant_id = participant["id"]

    rounds = get_knockout_rounds()
    matches = get_knockout_matches()
    predictions = get_knockout_predictions_for_participant(participant_id)
    final_prediction = get_knockout_final_prediction_for_participant(
        participant_id
    )

    predictions_by_match_id = {
        prediction["match_id"]: prediction
        for prediction in predictions
    }

    total_matches = len(matches)
    saved_count = len(predictions)

    st.metric("Sparade slutspelstips", f"{saved_count}/{total_matches}")

    st.subheader("Sparat finaltips")

    if final_prediction:
        st.markdown(f"**Finalist 1:** {final_prediction.get('finalist_1') or '-'}")
        st.markdown(f"**Finalist 2:** {final_prediction.get('finalist_2') or '-'}")
        st.markdown(f"**Vinnare:** {final_prediction.get('winner') or '-'}")
    else:
        st.info("Du har inget sparat finaltips ännu.")

    st.subheader("Sparade matchtips")

    if not predictions:
        st.info("Du har inga sparade slutspelstips ännu.")
        return

    st.caption("Tipsen nedan är hämtade från det som är sparat just nu.")

    view_filter = st.radio(
        "Visa",
        options=["Endast tippade matcher", "Alla matcher"],
        horizontal=True,
        key="saved_knockout_predictions_filter",
    )

    round_name_by_id = {
        knockout_round["id"]: knockout_round["name"]
        for knockout_round in rounds
    }

    last_round_name = None

    for match in matches:
        prediction = predictions_by_match_id.get(match["id"])

        if view_filter == "Endast tippade matcher" and prediction is None:
            continue

        round_name = round_name_by_id.get(match["round_id"], "Okänd runda")

        if round_name != last_round_name:
            st.markdown(f"### {round_name}")
            last_round_name = round_name

        kickoff_at = match.get("kickoff_at")

        kickoff_text = (
            format_datetime_swedish(kickoff_at)
            if kickoff_at
            else "Avspark ej satt"
        )

        with st.container(border=True):
            st.caption(
                f"Match {match['match_no']} · {kickoff_text}"
            )

            st.markdown(
                f"### {match['home_team']} – {match['away_team']}"
            )

            if prediction:
                predicted_home_goals = prediction["predicted_home_goals"]
                predicted_away_goals = prediction["predicted_away_goals"]

                predicted_outcome = get_match_outcome(
                    int(predicted_home_goals),
                    int(predicted_away_goals),
                )

                st.markdown("**Ditt sparade tips:**")

                st.markdown(
                    f"### {predicted_home_goals}–{predicted_away_goals} "
                    f"({predicted_outcome}) · "
                    f"{format_goals_pick_label(prediction['goals_pick'])}"
                )

                first_scorer = prediction.get("first_scorer_pick") or "-"

                st.markdown("**Första målskytt:**")
                st.markdown(first_scorer)
            else:
                st.info("Inget sparat tips på denna match.")

def render_all_knockout_predictions_for_match(
    match: dict,
    participants: list[dict],
    predictions: list[dict],
) -> None:
    """
    Visar allas slutspelstips för en match.

    Visas endast när rundan är låst/stängd.
    """

    participant_name_by_id = {
        participant["id"]: participant["display_name"]
        for participant in participants
    }

    predictions_by_participant_id = {
        prediction["participant_id"]: prediction
        for prediction in predictions
        if prediction["match_id"] == match["id"]
    }

    rows = []

    for participant in participants:
        participant_id = participant["id"]
        prediction = predictions_by_participant_id.get(participant_id)

        if prediction:
            predicted_home_goals = prediction["predicted_home_goals"]
            predicted_away_goals = prediction["predicted_away_goals"]

            predicted_outcome = get_match_outcome(
                int(predicted_home_goals),
                int(predicted_away_goals),
            )

            tip_text = (
                f"{predicted_home_goals}–{predicted_away_goals} "
                f"({predicted_outcome})"
            )

            goals_text = format_goals_pick_label(prediction["goals_pick"])
            first_scorer_text = prediction.get("first_scorer_pick") or "-"

            if is_finished_knockout_match(match):
                score = calculate_knockout_match_points(
                    prediction=prediction,
                    match=match,
                )

                points_text = (
                    f"{score['points']}/8 "
                    f"({score['outcome_points']}p 1X2, "
                    f"{score['goals_points']}p Ö/U, "
                    f"{score['exact_result_points']}p exakt, "
                    f"{score['first_scorer_points']}p målskytt)"
                )
            else:
                points_text = "-"

        else:
            tip_text = "-"
            goals_text = "-"
            first_scorer_text = "-"
            points_text = "-"

        rows.append(
            {
                "Deltagare": participant_name_by_id.get(
                    participant_id,
                    "Okänd deltagare",
                ),
                "Resultat": tip_text,
                "Över/under": goals_text,
                "Första målskytt": first_scorer_text,
                "Poäng": points_text,
            }
        )

    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
    )

def render_knockout_matches_overview() -> None:
    """
    Visar slutspelsmatcher för deltagaren.

    Detta är en read-only översikt över matcher, resultat och allas tips
    när rundan är låst.
    """

    matches = get_knockout_matches()

    if not matches:
        st.info("Inga slutspelsmatcher är inlagda ännu.")
        return
    
    st.caption(
        "Allas tips visas per match när respektive rundas deadline har passerat "
        "eller när rundan är låst."
    )

    participants = get_active_participants()
    all_predictions = get_all_knockout_predictions()

    last_round_name = None

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        round_name = round_info.get("name", "Okänd runda")
        round_status = round_info.get("status", "not_started")

        if round_name != last_round_name:
            st.subheader(round_name)
            last_round_name = round_name

        kickoff_at = match.get("kickoff_at")

        kickoff_text = (
            format_datetime_swedish(kickoff_at)
            if kickoff_at
            else "Avspark ej satt"
        )

        with st.container(border=True):
            st.caption(
                f"Match {match['match_no']} · {kickoff_text}"
            )

            st.markdown(
                f"### {format_knockout_match_result_text(match)}"
            )

            if is_finished_knockout_match(match):
                actual_first_scorer = match.get("first_scorer")

                if actual_first_scorer:
                    st.markdown(f"**Första målskytt:** {actual_first_scorer}")
            else:
                st.info("Resultat är inte ifyllt ännu.")

            round_deadline_at = round_info.get("deadline_at")

            round_deadline_passed = (
                is_deadline_passed(round_deadline_at)
                if round_deadline_at
                else False
            )

            round_is_public = (
                round_status in {"locked", "finished"}
                or round_deadline_passed
            )

            if round_is_public:
                with st.expander("Visa allas tips på matchen"):
                    render_all_knockout_predictions_for_match(
                        match=match,
                        participants=participants,
                        predictions=all_predictions,
                    )

def render_locked_knockout_prediction_card(
    match: dict,
    existing_prediction: dict | None,
) -> None:
    """
    Visar ett kompakt read-only-kort för en låst slutspelsmatch.

    Kortet visar:
    - match/resultat
    - deltagarens tips
    - rätt rad om resultat finns
    - poäng per match
    """

    kickoff_at = match.get("kickoff_at")

    kickoff_text = (
        format_datetime_swedish(kickoff_at)
        if kickoff_at
        else "Avspark ej satt"
    )

    st.caption(
        f"Match {match['match_no']} · {kickoff_text} svensk tid."
    )

    st.markdown(
        f"### {format_knockout_match_result_text(match)}"
    )

    if existing_prediction is None:
        st.warning("Du har inget sparat tips på denna match.")
        return

    predicted_home_goals = existing_prediction["predicted_home_goals"]
    predicted_away_goals = existing_prediction["predicted_away_goals"]
    predicted_outcome = get_prediction_outcome_text(existing_prediction)

    st.markdown(
        "**Ditt tips:** "
        f"{predicted_home_goals}–{predicted_away_goals} "
        f"({predicted_outcome}) · "
        f"{format_goals_pick_label(existing_prediction['goals_pick'])}"
    )

    first_scorer = existing_prediction.get("first_scorer_pick") or "-"
    st.markdown(f"**Din första målskytt:** {first_scorer}")

    if not is_finished_knockout_match(match):
        st.info("Resultat är inte ifyllt ännu.")
        return

    home_goals = int(match["home_goals_ft"])
    away_goals = int(match["away_goals_ft"])

    correct_outcome = get_match_outcome(home_goals, away_goals)
    correct_goals_pick = get_goals_pick(home_goals, away_goals)

    st.markdown(
        f"**Rätt rad:** {correct_outcome} · "
        f"{format_goals_pick_label(correct_goals_pick)}"
    )

    actual_first_scorer = match.get("first_scorer")

    if actual_first_scorer:
        st.markdown(f"**Rätt första målskytt:** {actual_first_scorer}")

    score = calculate_knockout_match_points(
        prediction=existing_prediction,
        match=match,
    )

    st.markdown("**Poäng**")
    st.markdown(f"## {score['points']}/8")

    st.caption(
        f"{score['outcome_points']}p för 1X2 · "
        f"{score['goals_points']}p för över/under · "
        f"{score['exact_result_points']}p för exakt resultat · "
        f"{score['first_scorer_points']}p för första målskytt"
    )

def render_read_only_knockout_round_predictions(
    matches: list[dict],
    predictions_by_match_id: dict,
) -> None:
    """
    Visar slutspelstips i read-only-läge.

    Används när rundan inte är öppen för ändringar.
    """

    for match in matches:
        existing = predictions_by_match_id.get(match["id"])

        with st.container(border=True):
            render_locked_knockout_prediction_card(
                match=match,
                existing_prediction=existing,
            )

def render_knockout_round_prediction_form(
    participant: dict,
    knockout_round: dict,
) -> None:
    """
    Visar tipsformulär för en slutspelsrunda.

    Deltagaren tippar:
    - exakt resultat efter fulltid
    - över/under 2,5 mål
    - första målskytt
    """

    round_id = knockout_round["id"]
    participant_id = participant["id"]

    matches = get_knockout_matches_for_round(round_id)

    if not matches:
        st.info("Inga matcher är inlagda för denna runda ännu.")
        return

    round_is_open = is_knockout_round_open_for_predictions(knockout_round)

    existing_predictions = get_knockout_predictions_for_participant(
        participant_id,
    )

    predictions_by_match_id = {
        prediction["match_id"]: prediction
        for prediction in existing_predictions
    }

    deadline_at = knockout_round.get("deadline_at")

    if deadline_at:
        st.caption(
            f"Deadline: {format_datetime_swedish(deadline_at)} svensk tid"
        )
    else:
        st.caption("Deadline: ej satt")

    if round_is_open:
        st.success("Rundan är öppen för tips.")
        st.caption(
            "Du kan spara de matcher du har fyllt i. "
            "Helt tomma matcher lämnas osparade och kan fyllas i senare."
        )
    else:
        st.warning("Rundan är inte öppen för ändringar.")

        render_read_only_knockout_round_predictions(
            matches=matches,
            predictions_by_match_id=predictions_by_match_id,
        )

        return

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
    incomplete_matches = []
    invalid_goal_matches = []

    

    with st.form(f"knockout_predictions_form_{round_id}"):

        submitted_top = st.form_submit_button(
                "Spara slutspelstips",
                key=f"save_knockout_predictions_top_{round_id}",
            )

        for match in matches:
            existing = predictions_by_match_id.get(match["id"])

            with st.container(border=True):

                kickoff_at = match.get("kickoff_at")

                kickoff_text = (
                    format_datetime_swedish(kickoff_at)
                    if kickoff_at
                    else "Avspark ej satt"
                )

                st.caption(
                    f"Match {match['match_no']} · {kickoff_text} svensk tid"
                )

                st.markdown(
                    f"### {match['home_team']} – {match['away_team']}"
                )

                existing_home_goals = (
                    str(existing["predicted_home_goals"])
                    if existing and existing["predicted_home_goals"] is not None
                    else ""
                )

                existing_away_goals = (
                    str(existing["predicted_away_goals"])
                    if existing and existing["predicted_away_goals"] is not None
                    else ""
                )

                col1, col2 = st.columns(2)

                with col1:
                    predicted_home_goals_text = st.text_input(
                        f"Mål {match['home_team']}",
                        value=existing_home_goals,
                        key=f"ko_home_{match['id']}",
                    )

                with col2:
                    predicted_away_goals_text = st.text_input(
                        f"Mål {match['away_team']}",
                        value=existing_away_goals,
                        key=f"ko_away_{match['id']}",
                    )

                existing_goals_value = (
                    existing["goals_pick"]
                    if existing
                    else None
                )

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
                    key=f"ko_goals_{match['id']}",
                )

                first_scorer_pick = st.text_input(
                    "Första målskytt",
                    value=(
                        existing.get("first_scorer_pick") or ""
                        if existing
                        else ""
                    ),
                    placeholder="Exempel: Kylian Mbappé",
                    key=f"ko_first_scorer_{match['id']}",
                )

                goals_pick = goals_label_to_value[goals_label]
                first_scorer_cleaned = first_scorer_pick.strip()

                home_goals_is_filled = predicted_home_goals_text.strip() != ""
                away_goals_is_filled = predicted_away_goals_text.strip() != ""
                goals_pick_is_filled = goals_pick is not None
                first_scorer_is_filled = first_scorer_cleaned != ""

                match_has_any_input = (
                    home_goals_is_filled
                    or away_goals_is_filled
                    or goals_pick_is_filled
                    or first_scorer_is_filled
                )

                match_is_complete = (
                    home_goals_is_filled
                    and away_goals_is_filled
                    and goals_pick_is_filled
                )

                if not match_has_any_input:
                    # Helt tom match: spara inget, men varna inte heller.
                    continue

                if not match_is_complete:
                    incomplete_matches.append(match["match_no"])
                    continue

                try:
                    predicted_home_goals = int(predicted_home_goals_text)
                    predicted_away_goals = int(predicted_away_goals_text)
                except ValueError:
                    invalid_goal_matches.append(match["match_no"])
                    continue

                if predicted_home_goals < 0 or predicted_away_goals < 0:
                    invalid_goal_matches.append(match["match_no"])
                    continue

                predictions_to_save.append(
                    {
                        "match_id": match["id"],
                        "predicted_home_goals": predicted_home_goals,
                        "predicted_away_goals": predicted_away_goals,
                        "goals_pick": goals_pick,
                        "first_scorer_pick": first_scorer_cleaned,
                    }
                )

        submitted_bottom = st.form_submit_button(
            "Spara slutspelstips",
            key=f"save_knockout_predictions_bottom_{round_id}",
        )

    submitted = submitted_top or submitted_bottom

    if submitted:
        if invalid_goal_matches:
            error_message = (
                "Vissa matcher har ogiltiga mål. "
                "Målfälten får bara innehålla heltal, till exempel 0, 1, 2 eller 3. "
                f"Kontrollera match: {', '.join(map(str, invalid_goal_matches))}"
            )

            st.toast(error_message, icon="⚠️")
            st.error(error_message)
            return
        
        if incomplete_matches:
            error_message = (
                "Vissa matcher är påbörjade men inte kompletta. "
                "Fyll i båda mål-fälten och över/under, eller lämna matchen helt tom. "
                f"Kontrollera match: {', '.join(map(str, incomplete_matches))}"
            )

            st.toast(error_message, icon="⚠️")
            st.error(error_message)
            return

        if not predictions_to_save:
            st.info("Inga kompletta slutspelstips att spara ännu.")
            return
        saved_predictions = save_knockout_predictions(
            participant_id=participant_id,
            predictions=predictions_to_save,
        )

        st.toast(
            f"Slutspelstips sparade ✅ ({len(saved_predictions)} matcher)",
            icon="✅",
        )

        st.success(
            f"Slutspelstips sparade för {len(saved_predictions)} matcher."
        )

def render_knockout_participant_section(
    participant: dict,
) -> None:
    """
    Huvudsektion för slutspel i deltagarvyn.

    Visar:
    - rundöversikt
    - tipsformulär per runda
    - matchöversikt
    """

    rounds = get_knockout_rounds()

    if not rounds:
        st.info("Slutspelet är inte förberett ännu.")
        return

    (
        tab_rounds,
        tab_predictions,
        tab_final,
        tab_saved_predictions,
        tab_matches,
        tab_leaderboard,
        tab_rules,
    ) = st.tabs(
        [
            "🏆 Rundor",
            "📝 Tips & resultat",
            "🏁 Finaltips",
            "✅ Sparade tips",
            "📅 Matcher",
            "📊 Tabell",
            "ℹ️ Regler",
        ]
    )

    with tab_rounds:
        render_knockout_rounds_overview()

    with tab_predictions:
        round_options = {
            knockout_round["id"]: knockout_round["name"]
            for knockout_round in rounds
        }

        selected_round_id = st.selectbox(
            "Välj runda",
            options=list(round_options.keys()),
            format_func=lambda round_id: round_options[round_id],
            key="knockout_participant_round_select",
        )

        selected_round = next(
            knockout_round
            for knockout_round in rounds
            if knockout_round["id"] == selected_round_id
        )

        render_knockout_round_prediction_form(
            participant=participant,
            knockout_round=selected_round,
        )

    with tab_final:
        render_knockout_final_prediction_section(participant)

    with tab_saved_predictions:
        render_saved_knockout_predictions_section(participant)


    with tab_matches:
        render_knockout_matches_overview()


    with tab_leaderboard:
        render_knockout_leaderboard_section()

    with tab_rules:
        render_knockout_rules_section()