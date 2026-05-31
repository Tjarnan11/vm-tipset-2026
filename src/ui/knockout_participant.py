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
    get_knockout_matches,
    get_knockout_matches_for_round,
    get_knockout_predictions_for_participant,
    get_knockout_rounds,
    save_knockout_predictions,
)
from src.time_utils import format_datetime_swedish
from src.ui.formatting import format_goals_pick_label

from src.ui.knockout_leaderboard import render_knockout_leaderboard_section

from src.ui.knockout_final import render_knockout_final_prediction_section



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

def render_knockout_rounds_overview() -> None:
    """
    Visar slutspelsrundor för deltagaren.
    """

    rounds = get_knockout_rounds()

    if not rounds:
        st.info("Slutspelet är inte förberett ännu.")
        return

    rows = []

    for knockout_round in rounds:
        deadline_at = knockout_round.get("deadline_at")

        rows.append(
            {
                "Runda": knockout_round["name"],
                "Deadline": (
                    format_datetime_swedish(deadline_at)
                    if deadline_at
                    else "-"
                ),
                "Status": knockout_round["status"],
            }
        )

    rounds_df = pd.DataFrame(rows)

    st.dataframe(
        rounds_df,
        width="stretch",
        hide_index=True,
    )


def render_knockout_matches_overview() -> None:
    """
    Visar slutspelsmatcher för deltagaren.

    Detta är en read-only översikt över matcher och resultat.
    """

    matches = get_knockout_matches()

    if not matches:
        st.info("Inga slutspelsmatcher är inlagda ännu.")
        return

    last_round_name = None

    for match in matches:
        round_info = match.get("knockout_rounds") or {}
        round_name = round_info.get("name", "Okänd runda")

        if round_name != last_round_name:
            st.subheader(round_name)
            last_round_name = round_name

        kickoff_at = match.get("kickoff_at")

        with st.container(border=True):
            st.caption(
                f"Match {match['match_no']}"
            )

            st.markdown(
                f"### {format_knockout_match_result_text(match)}"
            )

            if kickoff_at:
                st.caption(
                    f"Avspark: {format_datetime_swedish(kickoff_at)} svensk tid"
                )
            else:
                st.caption("Avspark: ej satt")

            if is_finished_knockout_match(match):
                st.success("Resultat efter fulltid är ifyllt.")
            else:
                st.info("Resultat är inte ifyllt ännu.")

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
        kickoff_at = match.get("kickoff_at")

        with st.container(border=True):
            st.caption(
                f"Match {match['match_no']}"
            )

            st.markdown(
                f"### {format_knockout_match_result_text(match)}"
            )

            if kickoff_at:
                st.caption(
                    f"Avspark: {format_datetime_swedish(kickoff_at)} svensk tid"
                )
            else:
                st.caption("Avspark: ej satt")

            if existing:
                st.markdown(
                    "**Ditt tips:** "
                    f"{existing['predicted_home_goals']}–"
                    f"{existing['predicted_away_goals']} · "
                    f"{format_goals_pick_label(existing['goals_pick'])}"
                )

                first_scorer = existing.get("first_scorer_pick") or "-"
                st.markdown(f"**Första målskytt:** {first_scorer}")
            else:
                st.info("Du har inget sparat tips på denna match.")

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
            "Alla matcher i rundan behöver ha över/under valt innan du kan spara."
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

    with st.form(f"knockout_predictions_form_{round_id}"):
        for match in matches:
            existing = predictions_by_match_id.get(match["id"])

            with st.container(border=True):
                st.caption(
                    f"Match {match['match_no']}"
                )

                st.markdown(
                    f"### {match['home_team']} – {match['away_team']}"
                )

                kickoff_at = match.get("kickoff_at")

                if kickoff_at:
                    st.caption(
                        f"Avspark: {format_datetime_swedish(kickoff_at)} svensk tid"
                    )
                else:
                    st.caption("Avspark: ej satt")

                existing_home_goals = (
                    int(existing["predicted_home_goals"])
                    if existing and existing["predicted_home_goals"] is not None
                    else 0
                )

                existing_away_goals = (
                    int(existing["predicted_away_goals"])
                    if existing and existing["predicted_away_goals"] is not None
                    else 0
                )

                col1, col2 = st.columns(2)

                with col1:
                    predicted_home_goals = st.number_input(
                        f"Mål {match['home_team']}",
                        min_value=0,
                        step=1,
                        value=existing_home_goals,
                        key=f"ko_home_{match['id']}",
                    )

                with col2:
                    predicted_away_goals = st.number_input(
                        f"Mål {match['away_team']}",
                        min_value=0,
                        step=1,
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

                if goals_pick is None:
                    incomplete_matches.append(match["match_no"])
                else:
                    predictions_to_save.append(
                        {
                            "match_id": match["id"],
                            "predicted_home_goals": int(predicted_home_goals),
                            "predicted_away_goals": int(predicted_away_goals),
                            "goals_pick": goals_pick,
                            "first_scorer_pick": first_scorer_pick.strip(),
                        }
                    )

        submitted = st.form_submit_button("Spara slutspelstips")

    if submitted:
        if incomplete_matches:
            st.error(
                "Vissa matcher saknar över/under-val: "
                f"{', '.join(map(str, incomplete_matches))}"
            )
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

    st.header("Slutspel")

    st.info(
        "Slutspelstipset är separat från gruppspelstipset. "
        "Du tippar varje slutspelsrunda när den öppnas."
    )

    rounds = get_knockout_rounds()

    if not rounds:
        st.info("Slutspelet är inte förberett ännu.")
        return

    (
        tab_rounds,
        tab_predictions,
        tab_final,
        tab_matches,
        tab_leaderboard,
    ) = st.tabs(
        [
            "🏆 Rundor",
            "📝 Tippa",
            "🏁 Finaltips",
            "📅 Matcher",
            "📊 Tabell",
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

    with tab_matches:
        render_knockout_matches_overview()


    with tab_leaderboard:
        render_knockout_leaderboard_section()