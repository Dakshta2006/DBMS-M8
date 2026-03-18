# backend/module_B8/services.py
#
# Business logic for Module 8 - Fever Evaluation.
# The time-series classification is now performed at the DATABASE level
# via a MongoDB aggregation pipeline (see database.py → classify_temperature_via_aggregation).
#
from typing import List, Dict, Any

from .schemas import FeverEpisodeCreate
from .database import (
    fetch_symptom_weights,
    fetch_disease_prevalence,
    save_fever_episode,
    classify_temperature_via_aggregation,
    update_episode_pattern,
    fetch_fuo_guidance,
)


# ─────────────────────────────────────────────
# Duration & Urgency helpers (pure Python — no DB needed)
# ─────────────────────────────────────────────

def categorize_duration(duration_days: int) -> str:
    """Module 8 Duration Categories."""
    if duration_days < 7:
        return "Acute (<7d)"
    elif 7 <= duration_days <= 21:
        return "Subacute (7-21d)"
    else:
        return "Chronic (>21d)"


def calculate_urgency(max_temp: float, pattern: str) -> str:
    """Module 8 Urgency Triage."""
    if max_temp >= 40.0 or pattern == "Hectic":
        return "High Urgency (Immediate Review)"
    elif max_temp >= 38.5:
        return "Moderate Urgency"
    else:
        return "Routine"


# ─────────────────────────────────────────────
# Bayesian Differential Diagnosis Engine
# ─────────────────────────────────────────────

async def run_bayesian_engine(symptoms: List[str]) -> List[Dict[str, Any]]:
    """
    Implements Bayes' Theorem for differential diagnosis:
      P(Disease | Symptoms) ∝ P(Disease) × ∏ P(Symptom_i | Disease)

    Reads P(Symptom|Disease) from `associated_symptoms` collection and
    base P(Disease) from `differential_diagnoses` collection.
    """
    if not symptoms:
        return []

    mappings          = await fetch_symptom_weights(symptoms)
    base_prevalences  = await fetch_disease_prevalence()

    # Build disease → {symptom: sensitivity} lookup
    disease_symptom_probs: Dict[str, Dict[str, float]] = {}
    for mapping in mappings:
        disease  = mapping["disease"]
        symp     = mapping["symptom"]
        sens     = mapping.get("sensitivity", 0.5)
        disease_symptom_probs.setdefault(disease, {})[symp] = sens

    # Compute unnormalised posterior scores
    results, total_score = [], 0.0
    for disease, symp_probs in disease_symptom_probs.items():
        prob = base_prevalences.get(disease, 0.01)
        for symp in symptoms:
            prob *= symp_probs.get(symp, 0.05)
        results.append({"disease": disease, "raw_score": prob})
        total_score += prob

    # Normalise to sum-to-1 probabilities
    if total_score == 0:
        return []

    differentials = [
        {
            "disease":     r["disease"],
            "probability": round(r["raw_score"] / total_score, 4),
        }
        for r in results
    ]
    differentials.sort(key=lambda x: x["probability"], reverse=True)
    return differentials


# ─────────────────────────────────────────────
# FUO Workup Guidance
# ─────────────────────────────────────────────

async def get_fuo_workup(duration_days: int, max_temp: float) -> List[Dict[str, Any]]:
    """
    If FUO criteria are met (fever >38.3 °C for >21 days),
    query the fuo_guidance lookup collection and return the structured
    ordered list of recommended clinical next steps.
    """
    if duration_days > 21 and max_temp > 38.3:
        return await fetch_fuo_guidance()
    return []


# ─────────────────────────────────────────────
# Main Episode Processing Pipeline
# ─────────────────────────────────────────────

async def process_and_save_episode(payload: FeverEpisodeCreate) -> Dict[str, Any]:
    """
    Full pipeline:
      1. Persist the raw episode document to MongoDB.
      2. Run DB-level aggregation to classify the temperature pattern
         (MAX / MIN / FLUCTUATION / AVG computed inside MongoDB).
      3. Patch the episode document with the DB-derived pattern + stats.
      4. Compute duration, urgency, and FUO flag.
      5. Run Bayesian differential diagnosis engine.
      6. If FUO, fetch the structured workup guidance from the lookup collection.
      7. Return the full enriched response.
    """
    # ── 1. Compute basic time-span from the payload timestamps ──
    temps_sorted = sorted(payload.temperatures, key=lambda t: t.timestamp)
    start_ts     = temps_sorted[0].timestamp
    end_ts       = temps_sorted[-1].timestamp
    duration_days = max((end_ts - start_ts).days, 0)

    # ── 2. Preliminary urgency (will be refined after DB aggregation) ──
    max_temp_py = max(t.temperature for t in temps_sorted)

    # ── 3. FUO flag ──
    fuo_risk = duration_days > 21 and max_temp_py > 38.3

    # ── 4. Bayesian differentials ──
    differentials = await run_bayesian_engine(payload.symptoms)

    # ── 5. Persist episode document ──
    episode_document = {
        "patient_id":      payload.patient_id,
        "patient_meta":    payload.patient_meta.model_dump(),
        "duration_days":   duration_days,
        "fuo_risk":        fuo_risk,
        "symptoms":        payload.symptoms,
        "differentials":   differentials,
        "notes":           payload.notes,
        # Store readings as embedded array — enables the aggregation pipeline
        "temperatures":    [t.model_dump() for t in temps_sorted],
        # pattern / urgency / temp_stats updated below after DB aggregation
        "pattern":         "Pending",
        "duration_category": categorize_duration(duration_days),
        "urgency_level":   "Pending",
    }
    episode_id = await save_fever_episode(episode_document)

    # ── 6. DB-level time-series aggregation (the core SQL-requirement) ──
    #      Runs MAX / MIN / AVG / FLUCTUATION + $switch CASE entirely inside MongoDB
    temp_stats = await classify_temperature_via_aggregation(episode_id)
    db_pattern = temp_stats.get("derived_pattern", "Unknown")
    db_max     = temp_stats.get("max_temp", max_temp_py)
    urgency    = calculate_urgency(db_max, db_pattern)

    # ── 7. Write the DB-computed pattern and stats back to the document ──
    await update_episode_pattern(episode_id, db_pattern, temp_stats)

    # ── 8. FUO workup guidance (from lookup collection) ──
    fuo_guidance = await get_fuo_workup(duration_days, db_max)

    # ── 9. Build response ──
    return {
        "episode_id":        episode_id,
        "patient_id":        payload.patient_id,
        "pattern":           db_pattern,
        "duration_days":     duration_days,
        "duration_category": categorize_duration(duration_days),
        "urgency_level":     urgency,
        "fuo_risk":          fuo_risk,
        "differentials":     differentials,
        "fuo_guidance":      fuo_guidance if fuo_guidance else None,
        "temp_stats":        temp_stats if temp_stats else None,
    }