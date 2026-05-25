# src/ui/participant_page.py
#
# Deltagarsidan:
# - välkomnar deltagaren
# - visar tabs
# - visar gruppspelstips
# - hanterar sparande av tips

import streamlit as st

from src.deadline import (
    format_deadline_swedish,
    is_deadline_passed,
)
from src.repositories.matches_repo import get_matches
from src.repositories.participants_repo import get_participant_by_token
from src.repositories.predictions_repo import (
    delete_predictions_for_matches,
    get_predictions_for_participant,
    save_predictions,
)
from src.repositories.settings_repo import get_group_stage_deadline
from src.scoring import (
    calculate_prediction_points,
    get_goals_pick,
    get_match_outcome,
    is_finished_match,
)
from src.time_utils import (
    format_date_swedish,
    format_datetime_swedish,
)
from src.ui.bonus import render_bonus_prediction_section
from src.ui.formatting import (
    format_goals_pick_label,
    format_match_result_text,
)
from src.ui.leaderboard_page import (
    render_leaderboard_section,
    render_public_predictions_overview_section,
)
from src.ui.results_page import render_public_matches_results_section
from src.ui.rules import render_rules_section

from src.ui.knockout_participant import render_knockout_participant_section


def render_locked_prediction_card(
    match: dict,
    existing_prediction: dict | None,
) -> None:
    """
    Visar ett kompakt read-only-kort efter deadline.

    När deadline har passerat ska deltagaren inte se disabled dropdowns.
    I stället visar vi:
    - resultat om det finns
    - deltagarens tips
    - rätt rad
    - poäng på matchen
    """

    st.markdown(
        f"**Match {match['match_no']} · Grupp {match['group_name']} · "
        f"{format_datetime_swedish(match['kickoff_at'])}**"
    )

    st.markdown(
        f"### {format_match_result_text(match)}"
    )

    if existing_prediction is None:
        st.warning("Du har inget sparat tips på denna match.")
        return

    user_outcome = existing_prediction["outcome_pick"]
    user_goals = format_goals_pick_label(existing_prediction["goals_pick"])

    st.markdown(
        f"**Ditt tips:** {user_outcome} · {user_goals}"
    )

    if not is_finished_match(match):
        st.info("Resultat är inte ifyllt ännu.")
        return

    home_goals = int(match["home_goals"])
    away_goals = int(match["away_goals"])

    correct_outcome = get_match_outcome(home_goals, away_goals)
    correct_goals_pick = get_goals_pick(home_goals, away_goals)

    score = calculate_prediction_points(
        prediction=existing_prediction,
        match=match,
    )

    st.markdown(
        f"**Rätt rad:** {correct_outcome} · "
        f"{format_goals_pick_label(correct_goals_pick)}"
    )

    st.markdown("**Poäng**")

    st.markdown(
        f"## {score['points']}/2"
    )

    st.caption(
        f"{score['outcome_points']}p för 1X2 · "
        f"{score['goals_points']}p för över/under"
    )


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

        submitted_top = False

        if not predictions_locked:
            submitted_top = st.form_submit_button(
                "Spara ändringar",
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
                if predictions_locked:
                    render_locked_prediction_card(
                        match=match,
                        existing_prediction=existing,
                    )
                    continue

                st.markdown(
                    f"**Match {match['match_no']} · Grupp {match['group_name']}**"
                )

                st.markdown(
                    f"### {match['home_team']} – {match['away_team']}"
                )

                st.caption(
                    f"Avspark: {format_datetime_swedish(match['kickoff_at'])} svensk tid"
                )

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

        submitted_bottom = False

        if not predictions_locked:
            submitted_bottom = st.form_submit_button(
                "Spara ändringar",
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

    (
        tab_tips,
        tab_leaderboard,
        tab_predictions,
        tab_matches,
        tab_knockout,
        tab_rules,
    ) = st.tabs(
        [
            "📝 Mina tips",
            "📊 Poängtabell",
            "🧾 Allas tips",
            "📅 Matcher & resultat",
            "🏆 Slutspel",
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

    with tab_knockout:
        render_knockout_participant_section()

    with tab_rules:
        render_rules_section()
