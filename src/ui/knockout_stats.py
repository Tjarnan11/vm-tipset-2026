from __future__ import annotations

from collections import Counter, defaultdict
from math import log2

import pandas as pd
import streamlit as st

from src.deadline import is_deadline_passed
from src.knockout_scoring import calculate_knockout_match_points
from src.repositories.knockout_repo import (
    get_all_knockout_final_predictions,
    get_knockout_matches,
    get_knockout_predictions_for_matches,
    get_knockout_rounds,
)
from src.repositories.participants_repo import get_active_participants
from src.scoring import get_match_outcome


def _get_participant_name(participant: dict) -> str:
    return (
        participant.get("display_name")
        or participant.get("name")
        or "Okänd deltagare"
    )


def _get_match_round_id(match: dict) -> str | None:
    round_info = match.get("knockout_rounds") or {}
    return match.get("round_id") or round_info.get("id")


def _is_knockout_round_public(knockout_round: dict | None) -> bool:
    if not knockout_round:
        return False

    status = knockout_round.get("status")
    deadline_at = knockout_round.get("deadline_at")

    return status in {"locked", "finished"} or is_deadline_passed(deadline_at)


def _get_public_round_ids(rounds: list[dict]) -> set[str]:
    return {
        knockout_round["id"]
        for knockout_round in rounds
        if _is_knockout_round_public(knockout_round)
    }


def _get_public_match_ids(
    matches: list[dict],
    public_round_ids: set[str],
) -> list[str]:
    return [
        match["id"]
        for match in matches
        if _get_match_round_id(match) in public_round_ids
    ]


def _get_public_knockout_predictions(
    matches: list[dict],
    public_round_ids: set[str],
) -> list[dict]:
    public_match_ids = _get_public_match_ids(
        matches,
        public_round_ids,
    )

    return get_knockout_predictions_for_matches(public_match_ids)


def _format_match_label(match: dict) -> str:
    match_number = match.get("match_no", "?")
    home_team = match.get("home_team", "Hemmalag")
    away_team = match.get("away_team", "Bortalag")

    return f"{match_number}. {home_team} - {away_team}"


def _get_match_number(match: dict) -> int:
    try:
        return int(match.get("match_no", 999))
    except (TypeError, ValueError):
        return 999


def _calculate_entropy(values: list[str]) -> float:
    if not values:
        return 0.0

    counter = Counter(values)
    total = sum(counter.values())
    entropy = 0.0

    for count in counter.values():
        probability = count / total
        entropy -= probability * log2(probability)

    return entropy


def _is_finished_knockout_match(match: dict) -> bool:
    return (
        match.get("status") == "finished"
        and match.get("home_goals_ft") is not None
        and match.get("away_goals_ft") is not None
    )


def _build_public_prediction_rows(
    participants: list[dict],
    matches: list[dict],
    predictions: list[dict],
    public_round_ids: set[str],
) -> list[dict]:
    participants_by_id = {
        participant["id"]: participant
        for participant in participants
    }
    matches_by_id = {
        match["id"]: match
        for match in matches
        if _get_match_round_id(match) in public_round_ids
    }

    rows = []

    for prediction in predictions:
        participant = participants_by_id.get(prediction.get("participant_id"))
        match = matches_by_id.get(prediction.get("match_id"))

        if not participant or not match:
            continue

        predicted_home_goals = prediction.get("predicted_home_goals")
        predicted_away_goals = prediction.get("predicted_away_goals")

        if predicted_home_goals is None or predicted_away_goals is None:
            continue

        try:
            predicted_home_goals = int(predicted_home_goals)
            predicted_away_goals = int(predicted_away_goals)
        except (TypeError, ValueError):
            continue

        outcome = get_match_outcome(predicted_home_goals, predicted_away_goals)
        exact_result = f"{predicted_home_goals}-{predicted_away_goals}"

        rows.append(
            {
                "participant_id": participant["id"],
                "participant": _get_participant_name(participant),
                "match_id": match["id"],
                "match_number": _get_match_number(match),
                "match": _format_match_label(match),
                "round_id": _get_match_round_id(match),
                "round_name": (match.get("knockout_rounds") or {}).get(
                    "name",
                    "Okänd runda",
                ),
                "outcome": outcome,
                "exact_result": exact_result,
                "goals_pick": prediction.get("goals_pick"),
                "first_scorer": (prediction.get("first_scorer_pick") or "").strip(),
            }
        )

    return rows


def _render_participant_profiles(df: pd.DataFrame) -> None:
    st.subheader("Deltagarprofiler")

    st.caption(
        "Visar hur varje deltagare har tippat i de offentliga slutspelsrundorna. "
        "Olika resultat betyder hur många olika exakta resultat personen har använt, "
        "till exempel 1-0, 2-1 eller 1-1."
    )

    rows = []

    for participant_name, participant_df in df.groupby("participant"):
        outcome_counter = Counter(participant_df["outcome"].dropna())
        goals_counter = Counter(participant_df["goals_pick"].dropna())

        rows.append(
            {
                "Deltagare": participant_name,
                "1": outcome_counter.get("1", 0),
                "X": outcome_counter.get("X", 0),
                "2": outcome_counter.get("2", 0),
                "Över": goals_counter.get("over", 0),
                "Under": goals_counter.get("under", 0),
                "Olika resultat": participant_df["exact_result"].nunique(),
            }
        )

    stats_df = pd.DataFrame(rows)

    if stats_df.empty:
        st.info("Ingen statistik att visa ännu.")
        return

    st.dataframe(
        stats_df.sort_values("Deltagare"),
        width="stretch",
        hide_index=True,
    )


def _render_round_stats(
    rounds: list[dict],
    matches: list[dict],
    df: pd.DataFrame,
    public_round_ids: set[str],
) -> None:
    st.subheader("Statistik per runda")

    st.caption(
        "Visar en sammanfattning per offentlig slutspelsrunda. Framtida rundor "
        "är inte med förrän respektive deadline har passerat eller rundan är låst."
    )

    public_matches = [
        match
        for match in matches
        if _get_match_round_id(match) in public_round_ids
    ]

    match_count_by_round_id = Counter(
        _get_match_round_id(match)
        for match in public_matches
    )

    rows = []

    sorted_public_rounds = [
        knockout_round
        for knockout_round in sorted(
            rounds,
            key=lambda item: item.get("sort_order", 999),
        )
        if knockout_round["id"] in public_round_ids
    ]

    for knockout_round in sorted_public_rounds:
        round_id = knockout_round["id"]
        round_df = df[df["round_id"] == round_id] if not df.empty else df

        outcome_counter = (
            Counter(round_df["outcome"].dropna())
            if not round_df.empty
            else Counter()
        )
        goals_counter = (
            Counter(round_df["goals_pick"].dropna())
            if not round_df.empty
            else Counter()
        )
        exact_counter = (
            Counter(round_df["exact_result"].dropna())
            if not round_df.empty
            else Counter()
        )

        total_outcomes = sum(outcome_counter.values())
        total_goals = sum(goals_counter.values())

        disagreement_values = []
        if not round_df.empty:
            for _, match_df in round_df.groupby("match_id"):
                disagreement_values.append(
                    _calculate_entropy(list(match_df["outcome"].dropna()))
                )

        average_disagreement = (
            round(sum(disagreement_values) / len(disagreement_values), 2)
            if disagreement_values
            else 0.0
        )

        most_common_exact = exact_counter.most_common(1)

        rows.append(
            {
                "Runda": knockout_round.get("name", "Okänd runda"),
                "Matcher": match_count_by_round_id.get(round_id, 0),
                "Tips": len(round_df),
                "Deltagare": round_df["participant"].nunique()
                if not round_df.empty
                else 0,
                "1 %": round(100 * outcome_counter.get("1", 0) / total_outcomes)
                if total_outcomes
                else 0,
                "X %": round(100 * outcome_counter.get("X", 0) / total_outcomes)
                if total_outcomes
                else 0,
                "2 %": round(100 * outcome_counter.get("2", 0) / total_outcomes)
                if total_outcomes
                else 0,
                "Över %": round(100 * goals_counter.get("over", 0) / total_goals)
                if total_goals
                else 0,
                "Under %": round(100 * goals_counter.get("under", 0) / total_goals)
                if total_goals
                else 0,
                "Olika resultat": len(exact_counter),
                "Vanligast resultat": most_common_exact[0][0]
                if most_common_exact
                else "-",
                "Oenighet snitt": average_disagreement,
            }
        )

    round_stats_df = pd.DataFrame(rows)

    if round_stats_df.empty:
        st.info("Ingen rundstatistik att visa ännu.")
        return

    st.dataframe(
        round_stats_df,
        width="stretch",
        hide_index=True,
    )

    st.markdown("##### Deltagarprofiler i vald runda")

    st.caption(
        "Här kan du välja en offentlig runda och se samma typ av profil som i "
        "huvudtabellen, men bara för den rundan."
    )

    if df.empty:
        st.info("Det finns inga sparade tips att visa per deltagare ännu.")
        return

    round_options = {
        knockout_round["id"]: knockout_round.get("name", "Okänd runda")
        for knockout_round in sorted_public_rounds
    }

    selected_round_id = st.selectbox(
        "Välj runda",
        options=list(round_options.keys()),
        format_func=lambda round_id: round_options[round_id],
        key="knockout_stats_round_select",
    )

    selected_round_df = df[df["round_id"] == selected_round_id]

    if selected_round_df.empty:
        st.info("Det finns inga sparade tips att visa för vald runda.")
        return

    rows = []

    for participant_name, participant_df in selected_round_df.groupby("participant"):
        outcome_counter = Counter(participant_df["outcome"].dropna())
        goals_counter = Counter(participant_df["goals_pick"].dropna())

        rows.append(
            {
                "Deltagare": participant_name,
                "1": outcome_counter.get("1", 0),
                "X": outcome_counter.get("X", 0),
                "2": outcome_counter.get("2", 0),
                "Över": goals_counter.get("over", 0),
                "Under": goals_counter.get("under", 0),
                "Olika resultat": participant_df["exact_result"].nunique(),
            }
        )

    st.dataframe(
        pd.DataFrame(rows).sort_values("Deltagare"),
        width="stretch",
        hide_index=True,
    )


def _render_match_distribution_stats(df: pd.DataFrame) -> None:
    st.subheader("Tipsfördelning per match")

    st.caption(
        "Visar hur gruppens tips är fördelade per match. Oenighet räknas på "
        "1/X/2-tipsen: 0.00 betyder att alla har samma tecken, medan ett högre "
        "värde betyder att gruppen är mer splittrad."
    )

    rows = []

    for (match_number, match_label), match_df in df.groupby(["match_number", "match"]):
        outcome_counter = Counter(match_df["outcome"].dropna())
        exact_counter = Counter(match_df["exact_result"].dropna())
        goals_counter = Counter(match_df["goals_pick"].dropna())

        total_outcomes = sum(outcome_counter.values())
        total_goals = sum(goals_counter.values())
        most_common_exact = exact_counter.most_common(1)

        if total_outcomes == 0:
            continue

        rows.append(
            {
                "Matchnummer": match_number,
                "Match": match_label,
                "1": outcome_counter.get("1", 0),
                "X": outcome_counter.get("X", 0),
                "2": outcome_counter.get("2", 0),
                "1 %": round(100 * outcome_counter.get("1", 0) / total_outcomes),
                "X %": round(100 * outcome_counter.get("X", 0) / total_outcomes),
                "2 %": round(100 * outcome_counter.get("2", 0) / total_outcomes),
                "Över": goals_counter.get("over", 0),
                "Under": goals_counter.get("under", 0),
                "Över %": round(100 * goals_counter.get("over", 0) / total_goals)
                if total_goals
                else 0,
                "Under %": round(100 * goals_counter.get("under", 0) / total_goals)
                if total_goals
                else 0,
                "Vanligast resultat": most_common_exact[0][0]
                if most_common_exact
                else "-",
                "Antal vanligast": most_common_exact[0][1]
                if most_common_exact
                else 0,
                "Olika resultat": len(exact_counter),
                "Oenighet": round(_calculate_entropy(list(match_df["outcome"])), 2),
            }
        )

    match_stats_df = pd.DataFrame(rows)

    if match_stats_df.empty:
        st.info("Ingen matchstatistik att visa ännu.")
        return

    tab_outcome, tab_goals, tab_exact = st.tabs(
        ["1/X/2", "Över/under", "Exakta resultat"]
    )

    with tab_outcome:
        st.caption(
            "Antal och procent för hemmaseger, kryss och bortaseger. "
            "Oenighet mäter hur spridda 1/X/2-tipsen är i matchen."
        )

        st.dataframe(
            match_stats_df.sort_values("Matchnummer")[
                ["Match", "1", "X", "2", "1 %", "X %", "2 %", "Oenighet"]
            ],
            width="stretch",
            hide_index=True,
        )

    with tab_goals:
        st.caption(
            "Antal och procent för över/under 2,5 mål efter ordinarie tid."
        )

        st.dataframe(
            match_stats_df.sort_values("Matchnummer")[
                ["Match", "Över", "Under", "Över %", "Under %"]
            ],
            width="stretch",
            hide_index=True,
        )

    with tab_exact:
        st.caption(
            "Vanligast resultat är det exakta resultat flest har tippat. "
            "Olika resultat visar hur många olika exakta resultat gruppen har "
            "valt i samma match."
        )
        st.dataframe(
            match_stats_df.sort_values(
                ["Olika resultat", "Oenighet", "Matchnummer"],
                ascending=[False, False, True],
            )[
                [
                    "Match",
                    "Vanligast resultat",
                    "Antal vanligast",
                    "Olika resultat",
                    "Oenighet",
                ]
            ],
            width="stretch",
            hide_index=True,
        )


def _render_uniqueness_stats(df: pd.DataFrame) -> None:
    st.subheader("Vem går mest emot gruppen?")

    st.caption(
        "Unikhet är bara en kul jämförelse. Högre värde betyder att deltagaren "
        "oftare har valt mindre populära tips jämfört med resten av gruppen."
    )

    match_outcome_counts: dict[str, Counter] = defaultdict(Counter)
    match_result_counts: dict[str, Counter] = defaultdict(Counter)

    for _, row in df.iterrows():
        match_outcome_counts[row["match_id"]][row["outcome"]] += 1
        match_result_counts[row["match_id"]][row["exact_result"]] += 1

    uniqueness_by_participant = defaultdict(float)
    exact_uniqueness_by_participant = defaultdict(float)

    for _, row in df.iterrows():
        match_id = row["match_id"]
        participant = row["participant"]

        total_outcomes = sum(match_outcome_counts[match_id].values())
        same_outcome = match_outcome_counts[match_id][row["outcome"]]
        uniqueness_by_participant[participant] += 1 - same_outcome / total_outcomes

        total_results = sum(match_result_counts[match_id].values())
        same_result = match_result_counts[match_id][row["exact_result"]]
        exact_uniqueness_by_participant[participant] += 1 - same_result / total_results

    rows = [
        {
            "Deltagare": participant,
            "1X2-unikhet": round(uniqueness_by_participant[participant], 2),
            "Resultat-unikhet": round(exact_uniqueness_by_participant[participant], 2),
        }
        for participant in sorted(uniqueness_by_participant)
    ]

    uniqueness_df = pd.DataFrame(rows)

    if uniqueness_df.empty:
        st.info("Ingen unikhetsstatistik att visa ännu.")
        return

    with st.expander("Hur räknas unikhetspoängen?"):
        st.markdown(
            """
            Unikhet visar hur ofta en deltagare valt mindre populära tips.

            För varje match räknas `1 - andelen deltagare med samma tips`.
            Poängen summeras över alla slutspelsmatcher vars runda är offentlig.
            """
        )

    st.dataframe(
        uniqueness_df.sort_values(
            ["Resultat-unikhet", "1X2-unikhet", "Deltagare"],
            ascending=[False, False, True],
        ),
        width="stretch",
        hide_index=True,
    )


def _build_match_points_df(
    participants: list[dict],
    matches: list[dict],
    predictions: list[dict],
    public_round_ids: set[str],
) -> pd.DataFrame:
    public_finished_matches = [
        match
        for match in matches
        if _get_match_round_id(match) in public_round_ids
        and _is_finished_knockout_match(match)
    ]

    public_finished_matches = sorted(
        public_finished_matches,
        key=lambda match: _get_match_number(match),
    )

    if not public_finished_matches:
        return pd.DataFrame()

    participants_by_id = {
        participant["id"]: participant
        for participant in participants
    }
    prediction_by_participant_and_match = {
        (prediction["participant_id"], prediction["match_id"]): prediction
        for prediction in predictions
    }

    cumulative_points = {
        participant_id: 0
        for participant_id in participants_by_id
    }
    rows = []

    for match in public_finished_matches:
        result_label = f"{match.get('home_goals_ft')}-{match.get('away_goals_ft')}"

        for participant_id, participant in participants_by_id.items():
            prediction = prediction_by_participant_and_match.get(
                (participant_id, match["id"])
            )

            score = (
                calculate_knockout_match_points(prediction, match)
                if prediction
                else {
                    "points": 0,
                    "outcome_points": 0,
                    "goals_points": 0,
                    "exact_result_points": 0,
                    "first_scorer_points": 0,
                }
            )

            cumulative_points[participant_id] += score["points"]

            rows.append(
                {
                    "Matchnummer": _get_match_number(match),
                    "Match": _format_match_label(match),
                    "Resultat": result_label,
                    "Deltagare": _get_participant_name(participant),
                    "Matchpoäng": score["points"],
                    "Totalpoäng": cumulative_points[participant_id],
                    "Rätt 1X2": score["outcome_points"] > 0,
                    "Rätt Ö/U": score["goals_points"] > 0,
                    "Exakt": score["exact_result_points"] > 0,
                    "Rätt målskytt": score["first_scorer_points"] > 0,
                }
            )

    return pd.DataFrame(rows)


def _build_goal_total_rows(
    participants: list[dict],
    matches: list[dict],
    predictions: list[dict],
    public_round_ids: set[str],
) -> list[dict]:
    participants_by_id = {
        participant["id"]: participant
        for participant in participants
    }
    matches_by_id = {
        match["id"]: match
        for match in matches
        if _get_match_round_id(match) in public_round_ids
        and _is_finished_knockout_match(match)
    }

    rows = []

    for prediction in predictions:
        participant = participants_by_id.get(prediction.get("participant_id"))
        match = matches_by_id.get(prediction.get("match_id"))

        if not participant or not match:
            continue

        try:
            predicted_goals = int(prediction["predicted_home_goals"]) + int(
                prediction["predicted_away_goals"]
            )
            actual_goals = int(match["home_goals_ft"]) + int(match["away_goals_ft"])
        except (KeyError, TypeError, ValueError):
            continue

        rows.append(
            {
                "participant_id": participant["id"],
                "Deltagare": _get_participant_name(participant),
                "round_id": _get_match_round_id(match),
                "Runda": (match.get("knockout_rounds") or {}).get(
                    "name",
                    "Okänd runda",
                ),
                "match_id": match["id"],
                "Matchnummer": _get_match_number(match),
                "Match": _format_match_label(match),
                "Tippade mål": predicted_goals,
                "Faktiska mål": actual_goals,
                "Skillnad": predicted_goals - actual_goals,
                "Absolut skillnad": abs(predicted_goals - actual_goals),
            }
        )

    return rows


def _render_goal_total_stats(
    rounds: list[dict],
    participants: list[dict],
    matches: list[dict],
    predictions: list[dict],
    public_round_ids: set[str],
) -> None:
    st.subheader("Tippade mål jämfört med faktiska mål")

    st.caption(
        "Räknar bara färdigspelade matcher i offentliga rundor. Tabellen visar "
        "hur många mål varje deltagare har tippat totalt jämfört med hur många "
        "mål matcherna faktiskt innehöll."
    )

    rows = _build_goal_total_rows(
        participants,
        matches,
        predictions,
        public_round_ids,
    )

    goals_df = pd.DataFrame(rows)

    if goals_df.empty:
        st.info(
            "Målstatistik visas när minst en offentlig slutspelsmatch är färdigspelad."
        )
        return

    summary_df = (
        goals_df.groupby("Deltagare")
        .agg(
            Matcher=("match_id", "count"),
            Tippade_mål=("Tippade mål", "sum"),
            Faktiska_mål=("Faktiska mål", "sum"),
            Skillnad=("Skillnad", "sum"),
            Avvikelse_match_för_match=("Absolut skillnad", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "Tippade_mål": "Tippade mål",
                "Faktiska_mål": "Faktiska mål",
                "Avvikelse_match_för_match": "Avvikelse match för match",
            }
        )
    )

    summary_df["Snitt tippade mål"] = (
        summary_df["Tippade mål"] / summary_df["Matcher"]
    ).round(2)
    summary_df["Snitt faktiska mål"] = (
        summary_df["Faktiska mål"] / summary_df["Matcher"]
    ).round(2)
    summary_df["_Absolut totalskillnad"] = summary_df["Skillnad"].abs()

    st.markdown("##### Totalt")
    st.caption(
        "Skillnad är tippade mål minus faktiska mål. Positivt värde betyder att "
        "deltagaren har tippat fler mål än det faktiskt blev totalt. "
        "Tabellen sorteras först på hur nära deltagaren är totalt, alltså "
        "lägst absolut skillnad. Avvikelse match för match summerar hur långt "
        "ifrån deltagaren var i varje enskild match, utan att över- och "
        "undertippade matcher tar ut varandra."
    )

    st.dataframe(
        summary_df.sort_values(
            [
                "_Absolut totalskillnad",
                "Avvikelse match för match",
                "Skillnad",
                "Deltagare",
            ],
            ascending=[True, True, True, True],
        )[
            [
                "Deltagare",
                "Matcher",
                "Tippade mål",
                "Faktiska mål",
                "Skillnad",
                "Avvikelse match för match",
                "Snitt tippade mål",
                "Snitt faktiska mål",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

    st.markdown("##### Per runda")

    sorted_public_rounds = [
        knockout_round
        for knockout_round in sorted(
            rounds,
            key=lambda item: item.get("sort_order", 999),
        )
        if knockout_round["id"] in public_round_ids
    ]

    round_options = {
        knockout_round["id"]: knockout_round.get("name", "Okänd runda")
        for knockout_round in sorted_public_rounds
    }

    selected_round_id = st.selectbox(
        "Välj runda för målstatistik",
        options=list(round_options.keys()),
        format_func=lambda round_id: round_options[round_id],
        key="knockout_goal_stats_round_select",
    )

    round_df = goals_df[goals_df["round_id"] == selected_round_id]

    if round_df.empty:
        st.info("Det finns inga färdigspelade matcher med tips i vald runda ännu.")
        return

    round_summary_df = (
        round_df.groupby("Deltagare")
        .agg(
            Matcher=("match_id", "count"),
            Tippade_mål=("Tippade mål", "sum"),
            Faktiska_mål=("Faktiska mål", "sum"),
            Skillnad=("Skillnad", "sum"),
            Avvikelse_match_för_match=("Absolut skillnad", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "Tippade_mål": "Tippade mål",
                "Faktiska_mål": "Faktiska mål",
                "Avvikelse_match_för_match": "Avvikelse match för match",
            }
        )
    )
    round_summary_df["_Absolut totalskillnad"] = round_summary_df["Skillnad"].abs()

    st.caption(
        "Samma jämförelse, men bara för den valda rundans färdigspelade matcher. "
        "Sorteringen börjar med lägst absolut totalskillnad."
    )

    st.dataframe(
        round_summary_df.sort_values(
            [
                "_Absolut totalskillnad",
                "Avvikelse match för match",
                "Skillnad",
                "Deltagare",
            ],
            ascending=[True, True, True, True],
        )[
            [
                "Deltagare",
                "Matcher",
                "Tippade mål",
                "Faktiska mål",
                "Skillnad",
                "Avvikelse match för match",
            ]
        ],
        width="stretch",
        hide_index=True,
    )


def _render_points_and_difficulty_stats(
    participants: list[dict],
    matches: list[dict],
    predictions: list[dict],
    public_round_ids: set[str],
) -> None:
    st.subheader("Poängform och svåraste matcher")

    st.caption(
        "Grafen visar deltagarnas slutspelspoäng efter varje färdigspelad match "
        "i offentliga rundor. Matchtabellerna visar vilka matcher gruppen som "
        "helhet har tippat bäst och sämst på."
    )

    points_df = _build_match_points_df(
        participants,
        matches,
        predictions,
        public_round_ids,
    )

    if points_df.empty:
        st.info(
            "Poängstatistik visas när minst en offentlig slutspelsmatch är färdigspelad."
        )
        return

    chart_df = points_df.pivot(
        index="Matchnummer",
        columns="Deltagare",
        values="Totalpoäng",
    ).sort_index()

    selected_participants = st.multiselect(
        "Deltagare i grafen",
        options=list(chart_df.columns),
        default=list(chart_df.columns),
        key="knockout_stats_points_participants",
    )

    if selected_participants:
        st.caption(
            "Alla deltagare visas från början. Välj färre namn för att jämföra "
            "specifika personer."
        )

        st.line_chart(
            chart_df[selected_participants],
            height=420,
            x_label="Matchnummer",
            y_label="Slutspelspoäng",
        )
    else:
        st.info("Välj minst en deltagare för att visa grafen.")

    st.markdown("##### Gruppens bästa och svåraste matcher")

    participant_count = points_df["Deltagare"].nunique()
    max_points = participant_count * 8

    match_summary_df = (
        points_df.groupby(["Matchnummer", "Match", "Resultat"])
        .agg(
            Grupppoäng=("Matchpoäng", "sum"),
            Exakta=("Exakt", "sum"),
            Rätt_1X2=("Rätt 1X2", "sum"),
            Rätt_målskytt=("Rätt målskytt", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "Rätt_1X2": "Rätt 1X2",
                "Rätt_målskytt": "Rätt målskytt",
            }
        )
    )

    match_summary_df["Maxpoäng"] = max_points
    match_summary_df["Poängandel"] = (
        100 * match_summary_df["Grupppoäng"] / match_summary_df["Maxpoäng"]
    ).round().astype(int)

    tab_best, tab_hardest = st.tabs(["Bäst tippade", "Svåraste"])

    visible_columns = [
        "Match",
        "Resultat",
        "Grupppoäng",
        "Maxpoäng",
        "Poängandel",
        "Exakta",
        "Rätt 1X2",
        "Rätt målskytt",
    ]

    with tab_best:
        st.caption(
            "Matcherna där gruppen tillsammans har tagit flest poäng av möjliga "
            "poäng."
        )

        st.dataframe(
            match_summary_df.sort_values(
                ["Grupppoäng", "Exakta", "Matchnummer"],
                ascending=[False, False, True],
            )[visible_columns],
            width="stretch",
            hide_index=True,
        )

    with tab_hardest:
        st.caption(
            "Matcherna där gruppen tillsammans har tagit minst poäng av möjliga "
            "poäng."
        )

        st.dataframe(
            match_summary_df.sort_values(
                ["Grupppoäng", "Exakta", "Matchnummer"],
                ascending=[True, True, True],
            )[visible_columns],
            width="stretch",
            hide_index=True,
        )


def _render_final_prediction_stats(
    rounds: list[dict],
    participants: list[dict],
) -> None:
    st.subheader("Finaltips")

    st.caption(
        "Visar hur gruppen har tippat finalister och VM-vinnare. Den här "
        "statistiken visas först när första slutspelsrundans deadline har passerat."
    )

    sorted_rounds = sorted(
        rounds,
        key=lambda knockout_round: knockout_round.get("sort_order", 999),
    )
    first_round = sorted_rounds[0] if sorted_rounds else None

    if not _is_knockout_round_public(first_round):
        st.info(
            "Finaltips-statistik visas när första slutspelsrundans deadline har passerat."
        )
        return

    final_predictions = get_all_knockout_final_predictions()

    if not final_predictions:
        st.info("Inga finaltips finns ännu.")
        return

    participant_ids = {participant["id"] for participant in participants}
    visible_predictions = [
        prediction
        for prediction in final_predictions
        if prediction.get("participant_id") in participant_ids
    ]

    finalist_counter = Counter()
    winner_counter = Counter()

    for prediction in visible_predictions:
        for key in ["finalist_1", "finalist_2"]:
            finalist = (prediction.get(key) or "").strip()
            if finalist:
                finalist_counter[finalist] += 1

        winner = (prediction.get("winner") or "").strip()
        if winner:
            winner_counter[winner] += 1

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### Populäraste finallag")
        finalist_rows = [
            {"Lag": team, "Tips": count}
            for team, count in finalist_counter.most_common()
        ]
        st.dataframe(pd.DataFrame(finalist_rows), width="stretch", hide_index=True)

    with col2:
        st.markdown("##### Populäraste vinnare")
        winner_rows = [
            {"Lag": team, "Tips": count}
            for team, count in winner_counter.most_common()
        ]
        st.dataframe(pd.DataFrame(winner_rows), width="stretch", hide_index=True)


def render_knockout_stats_section() -> None:
    st.header("Slutspelsstatistik")

    st.caption(
        "Statistiken bygger bara på slutspelstips från rundor vars deadline "
        "har passerat eller som är låsta."
    )

    with st.expander("Vad visas här?"):
        st.markdown(
            """
            Statistiken visar profiler, tipsfördelning, målstatistik, unikhet, poängform och finaltips för slutspelet.

            En framtida runda räknas inte med förrän just den rundans deadline har passerat eller rundan är låst/avslutad.
            Finaltips-statistik visas först när första slutspelsrundans deadline har passerat.
            """
        )

    rounds = get_knockout_rounds()
    participants = get_active_participants()
    matches = get_knockout_matches()

    if not participants:
        st.info("Det finns inga deltagare ännu.")
        return

    public_round_ids = _get_public_round_ids(rounds)

    if not public_round_ids:
        st.info(
            "Slutspelsstatistik visas när minst en rundas deadline har passerat."
        )
        return

    predictions = _get_public_knockout_predictions(
        matches,
        public_round_ids,
    )

    public_rows = _build_public_prediction_rows(
        participants,
        matches,
        predictions,
        public_round_ids,
    )
    df = pd.DataFrame(public_rows)

    (
        tab_profiles,
        tab_rounds,
        tab_matches,
        tab_goals,
        tab_unique,
        tab_points,
        tab_final,
    ) = st.tabs(
        [
            "Deltagarprofiler",
            "Rundor",
            "Matcher",
            "Mål",
            "Unikhet",
            "Poäng & form",
            "Finaltips",
        ]
    )

    with tab_profiles:
        if df.empty:
            st.info(
                "Det finns inga offentliga slutspelstips att visa statistik för ännu."
            )
        else:
            _render_participant_profiles(df)

    with tab_rounds:
        _render_round_stats(
            rounds,
            matches,
            df,
            public_round_ids,
        )

    with tab_matches:
        if df.empty:
            st.info(
                "Det finns inga offentliga slutspelstips att visa statistik för ännu."
            )
        else:
            _render_match_distribution_stats(df)

    with tab_goals:
        _render_goal_total_stats(
            rounds,
            participants,
            matches,
            predictions,
            public_round_ids,
        )

    with tab_unique:
        if df.empty:
            st.info(
                "Det finns inga offentliga slutspelstips att visa statistik för ännu."
            )
        else:
            _render_uniqueness_stats(df)

    with tab_points:
        _render_points_and_difficulty_stats(
            participants,
            matches,
            predictions,
            public_round_ids,
        )

    with tab_final:
        _render_final_prediction_stats(
            rounds,
            participants,
        )
