# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules.module_B8.api import router as b8_router
from modules.module_B8.database import seed_all_collections


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: seed all lookup + Bayesian collections if empty."""
    await seed_all_collections()
    print("[startup] init_db complete — all collections ready.")
    yield
    # (shutdown hooks can go here if needed)


app = FastAPI(
    title="Medical Copilot System – Module 8",
    description="Fever Evaluation: time-series classification, Bayesian diagnosis, FUO guidance",
    version="2.0.0",
    lifespan=lifespan,
)

# Allow the Streamlit frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(b8_router)