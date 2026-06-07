# src/ui/knockout_final.py
#
# UI för slutspelstipsens långtidstips:
# - finallag
# - finalvinnare

import streamlit as st

from src.deadline import is_deadline_passed
from src.repositories.knockout_repo import (
    get_all_knockout_final_predictions,
    get_knockout_final_prediction_for_participant,
    get_knockout_final_result,
    get_knockout_rounds,
    save_knockout_final_prediction,
    save_knockout_final_result,
    update_knockout_final_prediction_review,
)
from src.repositories.participants_repo import get_active_participants
from src.knockout_scoring import calculate_knockout_final_points
from src.time_utils import format_datetime_swedish

def format_winner_correct_status(value: bool | None) -> str:
    """
    Gör om winner_correct till admintext.
    """

    if value is True:
        return "Rätt"

    if value is False:
        return "Fel"

    return "Ej bedömt"


def parse_winner_correct_status(label: str) -> bool | None:
    """
    Gör om admintext till databasvärde.
    """

    if label == "Rätt":
        return True

    if label == "Fel":
        return False

    return None


def get_first_knockout_round() -> dict | None:
    """
    Hämtar första slutspelsrundan.

    Finaltipsen ska låsas när första slutspelsrundans deadline passerar.
    """

    rounds = get_knockout_rounds()

    if not rounds:
        return None

    return rounds[0]

def is_final_prediction_public() -> bool:
    """
    Kontrollerar om finaltipsen ska visas för alla.

    Finaltipsen ska bara vara offentliga när första slutspelsrundan
    är låst/färdig eller när dess deadline har passerat.

    Viktigt:
    - not_started ska inte vara publikt
    - open med deadline i framtiden ska inte vara publikt
    """

    rounds = get_knockout_rounds()

    if not rounds:
        return False

    first_round = sorted(
        rounds,
        key=lambda knockout_round: knockout_round["sort_order"],
    )[0]

    status = first_round.get("status", "not_started")
    deadline_at = first_round.get("deadline_at")

    deadline_passed = (
        is_deadline_passed(deadline_at)
        if deadline_at
        else False
    )

    return (
        status in {"locked", "finished"}
        or deadline_passed
    )

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

def render_all_knockout_final_predictions_section() -> None:
    """
    Visar allas finaltips efter att finaltipsen är låsta.
    """

    st.subheader("Allas finaltips")

    if not is_final_prediction_public():
        st.info("Allas finaltips visas när finaltipsen är låsta.")
        return

    participants = get_active_participants()
    final_predictions = get_all_knockout_final_predictions()

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    participant_name_by_id = {
        participant["id"]: participant["display_name"]
        for participant in participants
    }

    final_prediction_by_participant_id = {
        final_prediction["participant_id"]: final_prediction
        for final_prediction in final_predictions
    }

    rows = []

    for participant in participants:
        participant_id = participant["id"]
        final_prediction = final_prediction_by_participant_id.get(
            participant_id
        )

        if final_prediction:
            final_score = calculate_knockout_final_points(final_prediction)

            rows.append(
                {
                    "Deltagare": participant_name_by_id.get(
                        participant_id,
                        "Okänd deltagare",
                    ),
                    "Finalist 1": final_prediction.get("finalist_1") or "-",
                    "Finalist 2": final_prediction.get("finalist_2") or "-",
                    "Vinnare": final_prediction.get("winner") or "-",
                    "Rätt finallag": (
                        str(final_prediction.get("correct_finalists_count"))
                        if final_prediction.get("correct_finalists_count")
                        is not None
                        else "-"
                    ),
                    "Vinnare rätt": (
                        "Ja"
                        if final_prediction.get("winner_correct") is True
                        else (
                            "Nej"
                            if final_prediction.get("winner_correct") is False
                            else "-"
                        )
                    ),
                    "Poäng": str(final_score["points"]),
                }
            )
        else:
            rows.append(
                {
                    "Deltagare": participant_name_by_id.get(
                        participant_id,
                        "Okänd deltagare",
                    ),
                    "Finalist 1": "-",
                    "Finalist 2": "-",
                    "Vinnare": "-",
                    "Rätt finallag": "-",
                    "Vinnare rätt": "-",
                    "Poäng": "-",
                }
            )

    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Finalpoäng visas när admin har bedömt finaltipsen. "
        "5p per rätt finallag och 10p för rätt finalvinnare."
    )

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

        st.divider()

        render_all_knockout_final_predictions_section()

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

    st.divider()

    render_all_knockout_final_predictions_section()


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

def render_knockout_final_review_admin_section() -> None:
    """
    Admin bedömer deltagarnas finaltips manuellt.

    Detta används eftersom finaltips är fritext.
    """

    st.subheader("Bedöm finaltips")

    participants = get_active_participants()
    final_predictions = get_all_knockout_final_predictions()

    if not participants:
        st.info("Inga deltagare finns ännu.")
        return

    if not final_predictions:
        st.info("Inga finaltips finns ännu.")
        return

    participant_name_by_id = {
        participant["id"]: participant["display_name"]
        for participant in participants
    }

    rows = []

    for final_prediction in final_predictions:
        rows.append(
            {
                "Deltagare": participant_name_by_id.get(
                    final_prediction["participant_id"],
                    "Okänd deltagare",
                ),
                "Finalist 1": final_prediction.get("finalist_1") or "-",
                "Finalist 2": final_prediction.get("finalist_2") or "-",
                "Vinnare": final_prediction.get("winner") or "-",
                "Rätt finallag": (
                    str(final_prediction.get("correct_finalists_count"))
                    if final_prediction.get("correct_finalists_count")
                    is not None
                    else "Ej bedömt"
                ),
                "Vinnare rätt": format_winner_correct_status(
                    final_prediction.get("winner_correct")
                ),
            }
        )

    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Rätt finallag ger 5 poäng per lag. "
        "Rätt finalvinnare ger 10 poäng."
    )

    prediction_label_by_participant_id = {}

    for final_prediction in final_predictions:
        participant_id = final_prediction["participant_id"]
        participant_name = participant_name_by_id.get(
            participant_id,
            "Okänd deltagare",
        )

        finalist_1 = final_prediction.get("finalist_1") or "-"
        finalist_2 = final_prediction.get("finalist_2") or "-"
        winner = final_prediction.get("winner") or "-"

        prediction_label_by_participant_id[participant_id] = (
            f"{participant_name}: {finalist_1} / {finalist_2}, vinnare {winner}"
        )

    selected_participant_id = st.selectbox(
        "Välj deltagare att bedöma",
        options=list(prediction_label_by_participant_id.keys()),
        format_func=lambda participant_id: prediction_label_by_participant_id[
            participant_id
        ],
        key="final_review_participant_select",
    )

    selected_prediction = next(
        final_prediction
        for final_prediction in final_predictions
        if final_prediction["participant_id"] == selected_participant_id
    )

    current_correct_finalists_count = selected_prediction.get(
        "correct_finalists_count"
    )

    finalist_count_options = [
        "Ej bedömt",
        "0",
        "1",
        "2",
    ]

    if current_correct_finalists_count is None:
        finalist_count_index = 0
    else:
        finalist_count_index = finalist_count_options.index(
            str(current_correct_finalists_count)
        )

    selected_finalist_count_label = st.selectbox(
        "Antal rätt finallag",
        options=finalist_count_options,
        index=finalist_count_index,
        key="final_review_finalist_count",
    )

    winner_status_options = [
        "Ej bedömt",
        "Rätt",
        "Fel",
    ]

    current_winner_status = format_winner_correct_status(
        selected_prediction.get("winner_correct")
    )

    selected_winner_status = st.selectbox(
        "Finalvinnare",
        options=winner_status_options,
        index=winner_status_options.index(current_winner_status),
        key="final_review_winner_status",
    )

    if st.button("Spara finaltips-bedömning"):
        if selected_finalist_count_label == "Ej bedömt":
            correct_finalists_count = None
        else:
            correct_finalists_count = int(selected_finalist_count_label)

        winner_correct = parse_winner_correct_status(selected_winner_status)

        updated_prediction = update_knockout_final_prediction_review(
            participant_id=selected_participant_id,
            correct_finalists_count=correct_finalists_count,
            winner_correct=winner_correct,
        )

        if updated_prediction:
            st.success("Finaltips-bedömningen är sparad.")
            st.info("Ladda om sidan för att se uppdaterad slutspelstabell.")
        else:
            st.error("Kunde inte spara finaltips-bedömningen.")