# backend/module_B8/schemas.py
# Pydantic v2 models for Module 8 - Fever Evaluation
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime


# ─────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────

class PatientMeta(BaseModel):
    name: Optional[str] = None
    age: int = Field(..., ge=0, le=130, description="Patient age in years")
    gender: str = Field(..., description="Male / Female / Other / Unknown")
    comorbidities: Optional[str] = None


class TemperatureReading(BaseModel):
    timestamp: datetime = Field(..., description="ISO-8601 datetime of the reading")
    temperature: float = Field(..., ge=30.0, le=45.0, description="Temperature in Celsius")


class DifferentialDiagnosis(BaseModel):
    disease: str
    probability: float = Field(..., ge=0.0, le=1.0)


class FUOStep(BaseModel):
    """A single recommended clinical step when FUO criteria are met."""
    step_number: int
    category: str          # e.g. "Lab Test", "Imaging", "Specialist Referral"
    recommendation: str    # e.g. "Blood cultures x3 (aerobic + anaerobic)"


# ─────────────────────────────────────────────
# Aggregation result model (used in SQL-demo + analytics)
# ─────────────────────────────────────────────

class TemperatureStats(BaseModel):
    """Result of the DB-level aggregation pipeline for time-series characterisation."""
    model_config = ConfigDict(populate_by_name=True)

    max_temp: float
    min_temp: float
    fluctuation: float
    avg_temp: float
    reading_count: int
    # Optional: absent if the aggregation pipeline finds no readings for the episode
    derived_pattern: Optional[str] = None


# ─────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────

class FeverEpisodeCreate(BaseModel):
    patient_id: str = Field(..., description="Unique patient identifier (e.g. PT-123)")
    patient_meta: PatientMeta
    temperatures: List[TemperatureReading] = Field(..., min_length=1)
    symptoms: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class FeverEpisodeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    episode_id: str
    patient_id: str
    pattern: str
    duration_days: int
    duration_category: str      # Acute (<7d) / Subacute (7-21d) / Chronic (>21d)
    urgency_level: str          # Routine / Moderate Urgency / High Urgency (Immediate Review)
    fuo_risk: bool
    # Safe default: empty list when Bayesian engine returns nothing (empty collections)
    differentials: List[DifferentialDiagnosis] = Field(default_factory=list)
    fuo_guidance: Optional[List[FUOStep]] = None   # populated only when fuo_risk=True
    temp_stats: Optional[TemperatureStats] = None  # DB aggregation result for transparency


class PatternAnalyticsResponse(BaseModel):
    pattern: str
    count: int
    average_duration_days: Optional[float] = None
    avg_max_temp: Optional[float] = None
    fuo_count: Optional[int] = None


class SQLDemoResult(BaseModel):
    """Generic wrapper returned by the /sql-demo endpoints."""
    query_name: str
    description: str
    pipeline: List[dict]        # the MongoDB aggregation pipeline used
    results: List[dict]