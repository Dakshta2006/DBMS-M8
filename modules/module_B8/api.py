# backend/module_B8/api.py
from fastapi import APIRouter, HTTPException, status
from typing import List

from .schemas import FeverEpisodeCreate, FeverEpisodeResponse, PatternAnalyticsResponse, SQLDemoResult
from .services import process_and_save_episode
from .database import fetch_patient_episodes, fetch_pattern_analytics, run_sql_demo, SQL_DEMO_QUERIES

router = APIRouter(prefix="/api/b8", tags=["Module 8 - Fever Evaluation"])


# ── Core Episode Endpoints ────────────────────────────────────────────────────

@router.post(
    "/episodes",
    response_model=FeverEpisodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new fever episode for triage & diagnosis"
)
async def create_fever_episode(payload: FeverEpisodeCreate):
    """
    Full pipeline:
    1. Save episode → 2. Run DB aggregation (MAX/MIN/AVG/FLUCTUATION + pattern $switch)
    → 3. Bayesian differential diagnosis → 4. FUO guidance (if applicable)
    """
    try:
        return await process_and_save_episode(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/episodes/{patient_id}",
    summary="Fetch all fever episodes for a patient"
)
async def get_episodes(patient_id: str):
    try:
        return await fetch_patient_episodes(patient_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/analytics/patterns",
    response_model=List[PatternAnalyticsResponse],
    summary="Pattern analytics: GROUP BY pattern with COUNT, AVG duration, AVG max temp"
)
async def get_pattern_analytics():
    try:
        return await fetch_pattern_analytics()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not fetch analytics")


# ── SQL / Aggregation Demo Endpoints ─────────────────────────────────────────

@router.get(
    "/sql-demo/list",
    summary="List all available aggregation demo queries"
)
async def list_sql_demos():
    """Returns the names and descriptions of all available demo pipelines."""
    return [
        {"query_name": name, "description": meta["description"]}
        for name, meta in SQL_DEMO_QUERIES.items()
    ]


@router.get(
    "/sql-demo/{query_name}",
    response_model=SQLDemoResult,
    summary="Run a named aggregation demo pipeline and return results"
)
async def run_demo_query(query_name: str):
    """
    Executes one of the named MongoDB aggregation pipelines and returns
    the pipeline definition alongside live results from the DB.
    """
    result = await run_sql_demo(query_name)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown query '{query_name}'. Use /api/b8/sql-demo/list to see options."
        )
    return result