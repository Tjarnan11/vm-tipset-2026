# src/ui/knockout_final.py
#
# UI för slutspelstipsens långtidstips:
# - finallag
# - finalvinnare

import streamlit as st

from src.deadline import is_deadline_passed
from src.repositories.knockout_repo import (
    get_knockout_final_prediction_for_participant,
    get_knockout_final_result,
    get_knockout_rounds,
    save_knockout_final_prediction,
    save_knockout_final_result,
)
from src.time_utils import format_datetime_swedish


def get_first_knockout_round() -> dict | None:
    """
    Hämtar första slutspelsrundan.

    Finaltipsen ska låsas när första slutspelsrundans deadline passerar.
    """

    rounds = get_knockout_rounds()

    if not rounds:
        return None

    return rounds[0]


def is_final_prediction_open() -> bool:
    """
    Kontrollerar om finaltipsen är öppna.

    För MVP låser vi finaltipsen vid deadline för första slutspelsrundan.
    """

    first_round = get_first_knockout_round()

    if first_round is None:
        return False

    deadline_at = first_round.get("deadline_at")

    if not deadline_at:
        return False

    if first_round.get("status") != "open":
        return False

    return not is_deadline_passed(deadline_at)


def render_knockout_final_prediction_section(
    participant: dict,
) -> None:
    """
    Deltagarsektion för att tippa finalister och finalvinnare.
    """

    st.subheader("Finaltips")

    st.info(
        "Tippa vilka två lag som går till final och vilket lag som vinner finalen. "
        "Detta är ett långtidstips för slutspelet."
    )

    first_round = get_first_knockout_round()

    if first_round is None:
        st.warning("Slutspelsrundor är inte skapade ännu.")
        return

    deadline_at = first_round.get("deadline_at")

    if deadline_at:
        st.caption(
            "Finaltipsen låses vid första slutspelsrundans deadline: "
            f"{format_datetime_swedish(deadline_at)} svensk tid"
        )
    else:
        st.caption("Finaltipsens deadline är inte satt ännu.")

    participant_id = participant["id"]
    existing_prediction = get_knockout_final_prediction_for_participant(
        participant_id,
    )

    existing_finalist_1 = (
        existing_prediction.get("finalist_1", "")
        if existing_prediction
        else ""
    )

    existing_finalist_2 = (
        existing_prediction.get("finalist_2", "")
        if existing_prediction
        else ""
    )

    existing_winner = (
        existing_prediction.get("winner", "")
        if existing_prediction
        else ""
    )

    final_prediction_open = is_final_prediction_open()

    if not final_prediction_open:
        st.warning("Finaltipsen är inte öppna för ändringar.")

        if existing_prediction:
            st.markdown(f"**Finalist 1:** {existing_finalist_1 or '-'}")
            st.markdown(f"**Finalist 2:** {existing_finalist_2 or '-'}")
            st.markdown(f"**Vinnare:** {existing_winner or '-'}")
        else:
            st.info("Du har inget sparat finaltips.")

        return

    with st.form("knockout_final_prediction_form"):
        finalist_1 = st.text_input(
            "Finalist 1",
            value=existing_finalist_1,
            placeholder="Exempel: Brasilien",
        )

        finalist_2 = st.text_input(
            "Finalist 2",
            value=existing_finalist_2,
            placeholder="Exempel: Frankrike",
        )

        winner = st.text_input(
            "Vinnare",
            value=existing_winner,
            placeholder="Exempel: Brasilien",
        )

        submitted = st.form_submit_button("Spara finaltips")

    if submitted:
        cleaned_finalist_1 = finalist_1.strip()
        cleaned_finalist_2 = finalist_2.strip()
        cleaned_winner = winner.strip()

        if not cleaned_finalist_1 or not cleaned_finalist_2 or not cleaned_winner:
            st.error("Alla tre fält måste fyllas i.")
            return

        if cleaned_finalist_1.lower() == cleaned_finalist_2.lower():
            st.error("Finalist 1 och finalist 2 måste vara olika lag.")
            return

        winner_is_finalist = cleaned_winner.lower() in {
            cleaned_finalist_1.lower(),
            cleaned_finalist_2.lower(),
        }

        if not winner_is_finalist:
            st.error("Vinnaren måste vara ett av dina två finallag.")
            return

        saved_prediction = save_knockout_final_prediction(
            participant_id=participant_id,
            finalist_1=cleaned_finalist_1,
            finalist_2=cleaned_finalist_2,
            winner=cleaned_winner,
        )

        if saved_prediction:
            st.toast("Finaltips sparat ✅", icon="✅")
            st.success("Finaltipset är sparat.")
        else:
            st.error("Kunde inte spara finaltipset.")


def render_knockout_final_admin_section() -> None:
    """
    Adminsektion för faktiskt finalutfall.

    Detta används senare för att räkna poäng för:
    - rätt finallag
    - rätt finalvinnare
    """

    st.subheader("Finalutfall")

    st.info(
        "Här fyller admin i vilka lag som faktiskt spelade final "
        "och vilket lag som vann finalen."
    )

    existing_result = get_knockout_final_result()

    existing_finalist_1 = (
        existing_result.get("finalist_1", "")
        if existing_result
        else ""
    )

    existing_finalist_2 = (
        existing_result.get("finalist_2", "")
        if existing_result
        else ""
    )

    existing_winner = (
        existing_result.get("winner", "")
        if existing_result
        else ""
    )

    with st.form("knockout_final_result_form"):
        finalist_1 = st.text_input(
            "Faktisk finalist 1",
            value=existing_finalist_1,
        )

        finalist_2 = st.text_input(
            "Faktisk finalist 2",
            value=existing_finalist_2,
        )

        winner = st.text_input(
            "Faktisk vinnare",
            value=existing_winner,
        )

        submitted = st.form_submit_button("Spara finalutfall")

    if submitted:
        cleaned_finalist_1 = finalist_1.strip()
        cleaned_finalist_2 = finalist_2.strip()
        cleaned_winner = winner.strip()

        if not cleaned_finalist_1 or not cleaned_finalist_2 or not cleaned_winner:
            st.error("Alla tre fält måste fyllas i.")
            return

        if cleaned_finalist_1.lower() == cleaned_finalist_2.lower():
            st.error("Finalist 1 och finalist 2 måste vara olika lag.")
            return

        winner_is_finalist = cleaned_winner.lower() in {
            cleaned_finalist_1.lower(),
            cleaned_finalist_2.lower(),
        }

        if not winner_is_finalist:
            st.error("Vinnaren måste vara ett av finallagen.")
            return

        saved_result = save_knockout_final_result(
            finalist_1=cleaned_finalist_1,
            finalist_2=cleaned_finalist_2,
            winner=cleaned_winner,
        )

        if saved_result:
            st.success("Finalutfall sparat.")
        else:
            st.error("Kunde inte spara finalutfall.")