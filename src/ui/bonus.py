# src/ui/bonus.py
#
# UI för utslagsfrågan:
# "Vem gör flest mål i gruppspelet?"

import pandas as pd
import streamlit as st

from src.deadline import is_deadline_passed
from src.repositories.bonus_repo import (
    delete_bonus_prediction,
    get_all_bonus_predictions,
    get_bonus_prediction_for_participant,
    get_bonus_scorer_results,
    save_bonus_prediction,
    upsert_bonus_scorer_result,
)
from src.repositories.participants_repo import get_active_participants
from src.repositories.settings_repo import get_group_stage_deadline


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
