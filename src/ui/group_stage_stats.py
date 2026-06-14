from __future__ import annotations

from collections import Counter, defaultdict
from math import log2

import pandas as pd
import streamlit as st

from src.repositories.matches_repo import get_matches
from src.repositories.participants_repo import get_active_participants
from src.repositories.predictions_repo import get_all_predictions


def _get(row: dict, *keys: str, default=None):
    """
    Hämtar första nyckeln som finns i en dict.

    Gör statistikvyn lite mer tålig om vi råkar ha olika kolumnnamn
    i olika tabeller/funktioner.
    """
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]

    return default


def _format_match_label(match: dict) -> str:
    match_number = _get(
        match,
        "match_no",
        "match_number",
        "match_order",
        "number",
        default="?",
    )
    home_team = _get(match, "home_team", "home", default="Hemmalag")
    away_team = _get(match, "away_team", "away", default="Bortalag")

    return f"{match_number}. {home_team} – {away_team}"

def _get_match_number(match: dict) -> int:
    match_number = _get(
        match,
        "match_no",
        "match_number",
        "match_order",
        "number",
        default=999,
    )

    try:
        return int(match_number)
    except (TypeError, ValueError):
        return 999

def _calculate_entropy(values: list[str]) -> float:
    """
    Mäta oenighet.

    Låg entropy = många har tippat samma sak.
    Hög entropy = tipsen är utspridda.
    """
    if not values:
        return 0.0

    counter = Counter(values)
    total = sum(counter.values())

    entropy = 0.0

    for count in counter.values():
        probability = count / total
        entropy -= probability * log2(probability)

    return entropy


def _build_lookup_tables(
    participants: list[dict],
    matches: list[dict],
) -> tuple[dict, dict]:
    participants_by_id = {
        participant["id"]: participant
        for participant in participants
    }

    matches_by_id = {
        match["id"]: match
        for match in matches
    }

    return participants_by_id, matches_by_id


def _build_prediction_rows(
    predictions: list[dict],
    participants_by_id: dict,
    matches_by_id: dict,
) -> list[dict]:
    rows = []

    for prediction in predictions:
        participant_id = _get(prediction, "participant_id")
        match_id = _get(prediction, "match_id")

        participant = participants_by_id.get(participant_id, {})
        match = matches_by_id.get(match_id, {})

        participant_name = _get(
            participant,
            "name",
            "display_name",
            default="Okänd deltagare",
        )

        outcome = _get(
            prediction,
            "outcome_pick",
            "outcome",
            "predicted_outcome",
            "prediction",
            default=None,
        )

        goals_tip = _get(
            prediction,
            "goals_pick",
            "over_under",
            "predicted_over_under",
            "goals_prediction",
            default=None,
        )

        if outcome is None and goals_tip is None:
            continue

        rows.append(
            {
                "participant_id": participant_id,
                "participant": participant_name,
                "match_id": match_id,
                "match_number": _get_match_number(match),
                "match_label": _format_match_label(match),
                "outcome": outcome,
                "goals_tip": goals_tip,
            }
        )

    return rows


def _render_participant_profile_stats(df: pd.DataFrame) -> None:
    st.subheader("Deltagarprofiler")

    participant_rows = []

    for participant_name, participant_df in df.groupby("participant"):
        outcome_counter = Counter(participant_df["outcome"].dropna())
        goals_counter = Counter(participant_df["goals_tip"].dropna())

        participant_rows.append(
            {
                "Deltagare": participant_name,
                "1": outcome_counter.get("1", 0),
                "X": outcome_counter.get("X", 0),
                "2": outcome_counter.get("2", 0),
                "Över 2.5": goals_counter.get("over", 0)
                + goals_counter.get("Över", 0)
                + goals_counter.get("OVER", 0),
                "Under 2.5": goals_counter.get("under", 0)
                + goals_counter.get("Under", 0)
                + goals_counter.get("UNDER", 0),
            }
        )

    stats_df = pd.DataFrame(participant_rows)

    if stats_df.empty:
        st.info("Ingen statistik att visa ännu.")
        return

    stats_df = stats_df.sort_values("Deltagare")

    st.dataframe(
        stats_df,
        width="stretch",
        hide_index=True,
    )


def _render_match_distribution_stats(df: pd.DataFrame) -> None:
    st.subheader("Tipsfördelning per match")

    st.caption(
        "Här visas hur gruppen har tippat på varje match. "
        "Oenighet räknas bara på 1/X/2-tipsen."
    )

    match_rows = []

    for (match_number, match_label), match_df in df.groupby(
        ["match_number", "match_label"]
    ):
        total_outcomes = match_df["outcome"].dropna().count()
        outcome_counter = Counter(match_df["outcome"].dropna())

        total_goals = match_df["goals_tip"].dropna().count()
        goals_counter = Counter(match_df["goals_tip"].dropna())

        outcome_values = list(match_df["outcome"].dropna())
        disagreement = _calculate_entropy(outcome_values)

        if total_outcomes == 0:
            continue

        over_count = (
            goals_counter.get("over", 0)
            + goals_counter.get("Över", 0)
            + goals_counter.get("OVER", 0)
        )

        under_count = (
            goals_counter.get("under", 0)
            + goals_counter.get("Under", 0)
            + goals_counter.get("UNDER", 0)
        )

        match_rows.append(
            {
                "Match": match_label,
                "Matchnummer": match_number,
                "1": outcome_counter.get("1", 0),
                "X": outcome_counter.get("X", 0),
                "2": outcome_counter.get("2", 0),
                "1 %": round(100 * outcome_counter.get("1", 0) / total_outcomes),
                "X %": round(100 * outcome_counter.get("X", 0) / total_outcomes),
                "2 %": round(100 * outcome_counter.get("2", 0) / total_outcomes),
                "Över": over_count,
                "Under": under_count,
                "Över %": round(100 * over_count / total_goals)
                if total_goals
                else 0,
                "Under %": round(100 * under_count / total_goals)
                if total_goals
                else 0,
                "Oenighet": round(disagreement, 2),
            }
        )

    match_stats_df = pd.DataFrame(match_rows)

    if match_stats_df.empty:
        st.info("Ingen matchstatistik att visa ännu.")
        return
    
    match_stats_df = match_stats_df.sort_values("Matchnummer")

    tab_outcome, tab_goals, tab_agreement = st.tabs(
        [
            "1/X/2",
            "Över/under",
            "Enighet & oenighet",
        ]
    )

    with tab_outcome:
        st.markdown("#### 1/X/2 per match")

        st.dataframe(
            match_stats_df[
                [
                    "Match",
                    "1",
                    "X",
                    "2",
                    "1 %",
                    "X %",
                    "2 %",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    with tab_goals:
        st.markdown("#### Över/under 2.5 mål per match")

        st.dataframe(
            match_stats_df[
                [
                    "Match",
                    "Över",
                    "Under",
                    "Över %",
                    "Under %",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    with tab_agreement:
        st.markdown("#### Enighet och oenighet per match")

        st.caption(
            "Oenighet räknas på 1/X/2-tipsen. "
            "0.00 betyder att alla har tippat samma tecken. "
            "Högre värde betyder att tipsen är mer splittrade."
        )

        agreement_df = match_stats_df.copy()
        agreement_df["Största andel"] = agreement_df[
            ["1 %", "X %", "2 %"]
        ].max(axis=1)

        st.dataframe(
            agreement_df.sort_values(
                ["Oenighet", "Största andel", "Matchnummer"],
                ascending=[False, True, True],
            )[
                [
                    "Match",
                    "1 %",
                    "X %",
                    "2 %",
                    "Största andel",
                    "Oenighet",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        
def _render_uniqueness_stats(df: pd.DataFrame) -> None:
    st.subheader("Vem går mest emot gruppen?")

    match_outcome_counts: dict[str, Counter] = defaultdict(Counter)

    for _, row in df.dropna(subset=["outcome"]).iterrows():
        match_outcome_counts[row["match_id"]][row["outcome"]] += 1

    uniqueness_by_participant = defaultdict(float)

    for _, row in df.dropna(subset=["outcome"]).iterrows():
        match_id = row["match_id"]
        outcome = row["outcome"]
        participant = row["participant"]

        total_predictions_for_match = sum(match_outcome_counts[match_id].values())
        count_for_same_tip = match_outcome_counts[match_id][outcome]

        if total_predictions_for_match == 0:
            continue

        share_with_same_tip = count_for_same_tip / total_predictions_for_match

        uniqueness_score = 1 - share_with_same_tip
        uniqueness_by_participant[participant] += uniqueness_score

    rows = [
        {
            "Deltagare": participant,
            "Unikhetspoäng": round(score, 2),
        }
        for participant, score in uniqueness_by_participant.items()
    ]

    uniqueness_df = pd.DataFrame(rows)

    if uniqueness_df.empty:
        st.info("Ingen unikhetsstatistik att visa ännu.")
        return

    with st.expander("Hur räknas unikhetspoängen?"):
        st.markdown(
            """
            **Unikhetspoängen visar hur ofta en deltagare har valt mindre populära 1/X/2-tips.**
            Det är inte tävlingspoäng, utan bara en kul jämförelse.

            För varje match räknas poängen så här:

            `1 - andelen deltagare som tippade samma tecken`

            Exempel med 10 deltagare:

            - Om **9 av 10** tippar hemmaseger och du också tippar hemmaseger får du `1 - 9/10 = 0.10`
            - Om du är ensam om att tippa kryss i samma match får du `1 - 1/10 = 0.90`

            Poängen summeras sedan över alla gruppspelsmatcher.

            **Högre värde betyder alltså att deltagaren oftare går emot gruppen.**
            Unikhet räknas just nu bara på **1/X/2**, inte över/under.
            """
        )

    st.caption(
        "Högre värde betyder att deltagaren oftare har valt mindre populära 1/X/2-tips."
    )

    st.dataframe(
        uniqueness_df.sort_values("Unikhetspoäng", ascending=False),
        width="stretch",
        hide_index=True,
    )

def _get_actual_outcome(match: dict) -> str | None:
    home_goals = _get(match, "home_goals")
    away_goals = _get(match, "away_goals")

    if home_goals is None or away_goals is None:
        return None

    if home_goals > away_goals:
        return "1"

    if home_goals < away_goals:
        return "2"

    return "X"


def _get_actual_goals_pick(match: dict) -> str | None:
    home_goals = _get(match, "home_goals")
    away_goals = _get(match, "away_goals")

    if home_goals is None or away_goals is None:
        return None

    total_goals = int(home_goals) + int(away_goals)

    if total_goals > 2.5:
        return "over"

    return "under"


def _score_group_stage_prediction(prediction: dict, match: dict) -> int:
    actual_outcome = _get_actual_outcome(match)
    actual_goals_pick = _get_actual_goals_pick(match)

    if actual_outcome is None or actual_goals_pick is None:
        return 0

    outcome_pick = _get(prediction, "outcome_pick")
    goals_pick = _get(prediction, "goals_pick")

    points = 0

    if outcome_pick == actual_outcome:
        points += 1

    if goals_pick == actual_goals_pick:
        points += 1

    return points


def _render_points_over_time_stats(
    participants: list[dict],
    matches: list[dict],
    predictions: list[dict],
) -> None:
    st.subheader("Poängutveckling över tid")

    st.caption(
        "Grafen visar deltagarnas totalpoäng efter varje färdigspelad gruppspelsmatch."
    )

    finished_matches = [
        match
        for match in matches
        if _get(match, "status") == "finished"
        and _get(match, "home_goals") is not None
        and _get(match, "away_goals") is not None
    ]

    if not finished_matches:
        st.info("Poängutvecklingen visas när minst en match är färdigspelad.")
        return

    finished_matches = sorted(
        finished_matches,
        key=lambda match: (
            _get(match, "kickoff_at", default=""),
            _get_match_number(match),
        ),
    )

    participants_by_id = {
        participant["id"]: participant
        for participant in participants
    }

    prediction_by_participant_and_match = {
        (
            prediction["participant_id"],
            prediction["match_id"],
        ): prediction
        for prediction in predictions
    }

    cumulative_points = {
        participant_id: 0
        for participant_id in participants_by_id
    }

    rows = []

    for match in finished_matches:
        match_id = match["id"]
        match_number = _get_match_number(match)
        match_label = _format_match_label(match)

        for participant_id, participant in participants_by_id.items():
            prediction = prediction_by_participant_and_match.get(
                (participant_id, match_id)
            )

            if prediction:
                cumulative_points[participant_id] += _score_group_stage_prediction(
                    prediction,
                    match,
                )

            participant_name = _get(
                participant,
                "name",
                "display_name",
                default="Okänd deltagare",
            )

            rows.append(
                {
                    "Matchnummer": match_number,
                    "Match": match_label,
                    "Deltagare": participant_name,
                    "Poäng": cumulative_points[participant_id],
                }
            )

    points_df = pd.DataFrame(rows)

    if points_df.empty:
        st.info("Det finns ingen poängdata att visa ännu.")
        return

    chart_df = points_df.pivot(
        index="Matchnummer",
        columns="Deltagare",
        values="Poäng",
    ).sort_index()

    participant_names = list(chart_df.columns)

    selected_participants = st.multiselect(
        "Deltagare i grafen",
        options=participant_names,
        default=participant_names,
    )

    st.caption(
        "Alla deltagare visas från början. Välj färre namn för att jämföra specifika personer."
    )

    if selected_participants:
        st.line_chart(
            chart_df[selected_participants],
            height=420,
            x_label="Matchnummer",
            y_label="Totalpoäng",   
        )
    else:
        st.info("Välj minst en deltagare för att visa grafen.")

    
    latest_match_number = points_df["Matchnummer"].max()
    previous_match_number = (
        points_df[points_df["Matchnummer"] < latest_match_number]["Matchnummer"].max()
        if len(points_df["Matchnummer"].unique()) > 1
        else None
    )

    latest_rows = points_df[
        points_df["Matchnummer"] == latest_match_number
    ].copy()

    if previous_match_number is not None:
        previous_rows = points_df[
            points_df["Matchnummer"] == previous_match_number
        ][["Deltagare", "Poäng"]].rename(
            columns={"Poäng": "Poäng före senaste match"}
        )

        latest_rows = latest_rows.merge(
            previous_rows,
            on="Deltagare",
            how="left",
        )

        latest_rows["Poäng senaste match"] = (
            latest_rows["Poäng"]
            - latest_rows["Poäng före senaste match"].fillna(0)
        )
    else:
        latest_rows["Poäng senaste match"] = latest_rows["Poäng"]

    latest_rows = latest_rows.rename(
        columns={"Poäng": "Totalpoäng"}
    )

    st.markdown("#### Poäng efter senaste färdiga match")

    st.caption(
        "Den officiella placeringen visas i huvudtabellen, där även bonusmål och rätt 1/X/2 används vid lika poäng."
    )

    st.dataframe(
        latest_rows[
            [
                "Deltagare",
                "Totalpoäng",
                "Poäng senaste match",
            ]
        ].sort_values(
            ["Totalpoäng", "Poäng senaste match", "Deltagare"],
            ascending=[False, False, True],
        ),
        width="stretch",
        hide_index=True,
    )

    


def render_group_stage_stats_section() -> None:
    st.header("📈 Gruppspelsstatistik")

    st.caption(
        "Statistiken bygger på sparade gruppspelstips och påverkar inte poängräkning eller tips."
    )

    with st.expander("Vad betyder statistiken?"):
        st.markdown(
            """
            **Deltagarprofiler** visar hur varje deltagare har fördelat sina gruppspelstips:
            antal hemmasegrar (**1**), kryss (**X**), bortasegrar (**2**) samt över/under 2.5 mål.

            **Tipsfördelning per match** visar hur gruppen har tippat på varje match.
            Den är uppdelad i **1/X/2**, **över/under 2.5 mål** och **enighet/oenighet**.

            **Oenighet** mäter hur splittrade gruppens **1/X/2-tips** är i en match.
            **0.00** betyder att alla har tippat samma tecken.
            Ett högre värde betyder att tipsen är mer utspridda mellan 1, X och 2.

            **Unikhetspoäng** visar vem som oftare har valt mindre populära **1/X/2-tips** jämfört med gruppen.
            En mer detaljerad förklaring finns i fliken **Unikhet**.

            Oenighet och unikhet påverkar inte tävlingens poäng.
            Det är bara extra statistik.
            """
        )

    participants = get_active_participants()
    matches = get_matches()

    predictions = get_all_predictions()

    if not participants:
        st.info("Det finns inga deltagare ännu.")
        return

    if not predictions:
        st.info("Det finns inga sparade tips ännu.")
        return

    participants_by_id, matches_by_id = _build_lookup_tables(
        participants,
        matches,
    )

    rows = _build_prediction_rows(
        predictions,
        participants_by_id,
        matches_by_id,
    )

    df = pd.DataFrame(rows)

    if df.empty:
        st.info("Det finns inga tips att visa statistik för ännu.")
        return

    tab_profiles, tab_matches, tab_unique, tab_progress = st.tabs(
        [
            "Deltagarprofiler",
            "Matcher",
            "Unikhet",
            "Poäng över tid",
        ]
    )

    with tab_profiles:
        _render_participant_profile_stats(df)

    with tab_matches:
        _render_match_distribution_stats(df)

    with tab_unique:
        _render_uniqueness_stats(df)

    with tab_progress:
        _render_points_over_time_stats(
            participants,
            matches,
            predictions,
        )