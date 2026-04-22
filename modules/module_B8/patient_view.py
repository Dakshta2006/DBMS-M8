# modules/module_B8/patient_view.py
import asyncio
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import streamlit as st
from fastapi.encoders import jsonable_encoder

from modules.module_B8.database import (
    fetch_patient_episodes,
    fetch_pattern_analytics,
    run_sql_demo,
    seed_all_collections,
)
from modules.module_B8.schemas import FeverEpisodeCreate
from modules.module_B8.services import process_and_save_episode

# Thread pool for running async tasks without event loop conflicts
_executor = ThreadPoolExecutor(max_workers=1)


def _resolve_api_base_url() -> str:
    """
    Optional external backend URL.
    Priority:
      1) Streamlit secrets: FASTAPI_BACKEND_URL / API_BASE_URL
      2) Environment:      FASTAPI_BACKEND_URL / API_BASE_URL
    """
    for key in ("FASTAPI_BACKEND_URL", "API_BASE_URL"):
        try:
            if key in st.secrets and st.secrets[key]:
                return str(st.secrets[key]).rstrip("/")
        except Exception:
            # st.secrets can be unavailable in local dev if no secrets file exists
            pass

        value = os.getenv(key)
        if value:
            return value.rstrip("/")

    return ""


API_BASE_URL = _resolve_api_base_url()
USE_HTTP_BACKEND = bool(API_BASE_URL)


def _run_async(coro):
    """Run async coroutine in a separate thread with its own event loop."""
    def _run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    future = _executor.submit(_run_in_thread)
    return future.result()


@st.cache_resource(show_spinner=False)
def _init_local_backend() -> bool:
    """Seed required collections once per app process in direct mode."""
    _run_async(seed_all_collections())
    return True


def _create_episode(payload: dict) -> dict:
    if USE_HTTP_BACKEND:
        resp = requests.post(f"{API_BASE_URL}/episodes", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    _init_local_backend()
    model = FeverEpisodeCreate(**payload)
    data = _run_async(process_and_save_episode(model))
    return jsonable_encoder(data)


def _get_patient_episodes(patient_id: str):
    if USE_HTTP_BACKEND:
        resp = requests.get(f"{API_BASE_URL}/episodes/{patient_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    _init_local_backend()
    data = _run_async(fetch_patient_episodes(patient_id))
    return jsonable_encoder(data)


def _get_pattern_analytics():
    if USE_HTTP_BACKEND:
        resp = requests.get(f"{API_BASE_URL}/analytics/patterns", timeout=15)
        resp.raise_for_status()
        return resp.json()

    _init_local_backend()
    data = _run_async(fetch_pattern_analytics())
    return jsonable_encoder(data)


def _run_sql_demo(query_name: str) -> dict:
    if USE_HTTP_BACKEND:
        resp = requests.get(f"{API_BASE_URL}/sql-demo/{query_name}", timeout=20)
        resp.raise_for_status()
        return resp.json()

    _init_local_backend()
    data = _run_async(run_sql_demo(query_name))
    if data is None:
        raise ValueError(f"Unknown demo query: {query_name}")
    return jsonable_encoder(data)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _parse_manual_entries(rows_text: str) -> pd.DataFrame:
    """Parses pasted CSV-style temperature data into a Pandas DataFrame."""
    lines = [l.strip() for l in rows_text.splitlines() if l.strip()]
    rows = []
    for ln in lines:
        parts = ln.split(",")
        if len(parts) < 2:
            continue
        try:
            rows.append({
                "timestamp":   pd.to_datetime(parts[0].strip()),
                "temperature": float(parts[1].strip()),
            })
        except Exception:
            continue
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["timestamp", "temperature"])


def _df_to_serializable(df: pd.DataFrame) -> list:
    out = []
    if df is None or df.empty:
        return out
    for _, r in df.sort_values("timestamp").iterrows():
        ts = r["timestamp"]
        if pd.isna(ts):
            continue
        if not isinstance(ts, (pd.Timestamp, datetime)):
            ts = pd.to_datetime(ts)
        out.append({"timestamp": ts.isoformat(), "temperature": float(r["temperature"])})
    return out


def _urgency_color(level: str) -> str:
    if "High" in level:
        return "red"
    elif "Moderate" in level:
        return "orange"
    return "green"

# ─────────────────────────────────────────────
# Main Router
# ─────────────────────────────────────────────

def render_patient_module():
    mode = "External FastAPI" if USE_HTTP_BACKEND else "Direct (in-process backend)"
    st.caption(f"Backend mode: {mode}")

    tabs = st.tabs([
        "🏠 Fever Triage Input",
        "📤 My Episodes",
        "📊 Pattern Analytics",
        "🔗 ER Diagram",
        "📋 DB Schema",
        "🩺 FUO & Guidance",
        "🧪 Aggregation Queries",   # ← NEW: SQL / Aggregation Demo tab
    ])

    st.divider()
    with tabs[0]: _triage_input_tab()
    with tabs[1]: _my_episodes_tab()
    with tabs[2]: _analytics_tab()
    with tabs[3]: _er_tab()
    with tabs[4]: _collections_tab()
    with tabs[5]: _guidance_tab()
    with tabs[6]: _sql_demo_tab()
    st.divider()


# ─────────────────────────────────────────────
# Tab 1 – Fever Triage Input
# ─────────────────────────────────────────────

def _triage_input_tab():
    st.header("New Fever Episode & Triage")

    # ── Symptom hint ──────────────────────────────────────────────────────────
    with st.expander("💡 Supported symptoms for Bayesian engine", expanded=False):
        st.markdown("""
**Type any of these (comma separated) into the symptoms box:**

| Disease | Key Symptoms |
|---|---|
| Malaria | rigors, sweating, headache, myalgia, nausea, splenomegaly |
| Dengue Fever | headache, myalgia, rash, nausea, joint pain, retro-orbital pain |
| Typhoid Fever | headache, abdominal pain, constipation, diarrhea, rigors, fatigue |
| Influenza | headache, myalgia, cough, rigors, fatigue, sore throat |
| Tuberculosis | night sweats, weight loss, cough, fatigue, haemoptysis |
| Pyelonephritis | rigors, flank pain, nausea, vomiting, dysuria, fatigue |
| Infective Endocarditis | rigors, joint pain, sweating, fatigue, chest pain |
| Lymphoma | night sweats, weight loss, fatigue, itching, lymph node swelling |
""")

    with st.form("fever_form"):
        col1, col2 = st.columns(2)
        with col1:
            patient_id = st.text_input("Patient ID", placeholder="e.g., PT-123")
            age        = st.number_input("Age", min_value=0, max_value=130, value=30)
        with col2:
            gender        = st.selectbox("Gender", ["Unknown", "Female", "Male", "Other"])
            symptoms_text = st.text_input(
                "Associated Symptoms (comma separated)",
                placeholder="e.g., rigors, sweating, headache",
                value="rigors, sweating, headache",
            )

        st.markdown("### 📈 Time-Series Temperature Data")
        
        # ── Upload CSV Option ─────────────────────────────────────────────────
        st.subheader("Upload CSV File or manual entry")
        st.caption("Upload a CSV file with columns: **timestamp** and **temperature** — Format: `YYYY-MM-DDTHH:MM:SS`")
        uploaded_file = st.file_uploader(
            "Choose CSV file",
            type=["csv"],
            key="temp_csv"
        )
        
        st.caption("Paste: `YYYY-MM-DDTHH:MM, temperature_in_celsius`  — one reading per line.")
        manual = st.text_area(
            "Data Input",
            value=(
                "2026-03-15T08:00, 37.1\n"
                "2026-03-15T12:00, 39.5\n"
                "2026-03-15T16:00, 37.2\n"
                "2026-03-15T20:00, 39.8\n"
                "2026-03-16T08:00, 37.0\n"
                "2026-03-16T12:00, 40.1\n"
                "2026-03-16T16:00, 37.3\n"
                "2026-03-16T20:00, 39.6"
            ),
            height=160,
            key="manual_entry"
        )
        
        notes  = st.text_area("Clinical Notes (Optional)")
        submit = st.form_submit_button("▶ Run Diagnostics & Triage Engine", type="primary")

    if not submit:
        return

    # Parse data from CSV or manual entry (prioritize CSV if both provided)
    if uploaded_file:
        try:
            df_uploaded = pd.read_csv(uploaded_file)
            # Check if it has the expected columns
            if 'timestamp' not in df_uploaded.columns or 'temperature' not in df_uploaded.columns:
                # Try reading without header and assign column names
                uploaded_file.seek(0)  # Reset file pointer
                df_uploaded = pd.read_csv(uploaded_file, header=None)
                if len(df_uploaded.columns) >= 2:
                    df_uploaded.columns = ['timestamp', 'temperature']
                else:
                    st.error("CSV must have at least 2 columns (timestamp, temperature)")
                    return
            
            df = df_uploaded[['timestamp', 'temperature']].copy()
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            st.success(f"✅ CSV loaded: {len(df)} readings")
        except Exception as e:
            st.error(f"Error parsing CSV: {e}")
            return
    else:
        df = _parse_manual_entries(manual)
    if df.empty or not patient_id:
        st.error("⚠️ Valid Patient ID and at least one temperature reading are required.")
        return

    # ── Preview the curve before hitting the API ──────────────────────────────
    st.markdown("### 📉 Temperature Curve Preview")
    _plot_temp_curve(df, pattern_label=None)

    symptoms_list = [s.strip().lower() for s in symptoms_text.split(",") if s.strip()]

    payload = {
        "patient_id":   patient_id,
        "patient_meta": {"age": age, "gender": gender, "comorbidities": notes},
        "temperatures": _df_to_serializable(df),
        "symptoms":     symptoms_list,
    }

    try:
        with st.spinner("Saving episode → running DB aggregation → Bayesian engine..."):
            data = _create_episode(payload)

        st.success(f"✅ Evaluation complete — episode saved (ID: `{data['episode_id']}`)")

        # ── DB Aggregation Stats ───────────────────────────────────────────────
        if data.get("temp_stats"):
            ts = data["temp_stats"]
            st.markdown("### 🗄️ DB Aggregation Stats *(MAX / MIN / AVG — computed in MongoDB)*")
            st.caption(
                "`$unwind → $group → $addFields → $switch`  ≡  "
                "SQL `GROUP BY` with `MAX()`, `MIN()`, `AVG()`, `CASE WHEN`"
            )
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("MAX °C",      ts["max_temp"])
            c2.metric("MIN °C",      ts["min_temp"])
            c3.metric("Fluctuation", ts["fluctuation"])
            c4.metric("AVG °C",      ts["avg_temp"])
            c5.metric("COUNT",       ts["reading_count"])

            # Redraw the curve with the DB-detected pattern label
            st.markdown("### 📉 Temperature Curve — DB Classified")
            _plot_temp_curve(df, pattern_label=data.get("pattern"), stats=ts)

        # ── Triage Summary ────────────────────────────────────────────────────
        st.divider()
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("🌡️ Pattern",          data["pattern"])
        col_b.metric("📅 Duration",          data["duration_category"])
        uc = _urgency_color(data["urgency_level"])
        col_c.markdown(f"**⚠️ Urgency**\n\n:{uc}[**{data['urgency_level']}**]")

        # ── FUO Alert ─────────────────────────────────────────────────────────
        if data.get("fuo_risk"):
            st.error(
                "🚨 **CRITICAL ALERT: FEVER OF UNKNOWN ORIGIN (FUO)**\n\n"
                "Criteria met: fever >38.3 °C for >21 days. "
                "Advanced inpatient workup required immediately."
            )
            if data.get("fuo_guidance"):
                st.markdown("#### 🩺 FUO Workup Checklist")
                st.caption("From `fuo_guidance` lookup collection:")
                for step in data["fuo_guidance"]:
                    st.markdown(
                        f"**{step['step_number']}.** `{step['category']}` — {step['recommendation']}"
                    )

        # ── Bayesian Differentials ────────────────────────────────────────────
        st.divider()
        diffs = data.get("differentials", [])
        if diffs:
            _render_bayesian_results(diffs, symptoms_list)
        else:
            st.info(
                "💡 No Bayesian differentials returned — "
                "enter symptoms like `rigors, sweating, headache` to activate the engine."
            )

    except requests.exceptions.ConnectionError:
        st.error(
            "❌ Cannot connect to the configured FastAPI backend URL. "
            "Set `FASTAPI_BACKEND_URL` (or `API_BASE_URL`) in Streamlit secrets "
            "to your deployed API endpoint."
        )
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ API returned an error: {e.response.text}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")


# ─────────────────────────────────────────────
# Helper: Matplotlib temperature curve
# ─────────────────────────────────────────────

def _plot_temp_curve(df: "pd.DataFrame", pattern_label=None, stats=None):
    """Render a proper annotated temperature curve with matplotlib."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(10, 3.5))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    ts  = df["timestamp"].tolist()
    tmp = df["temperature"].tolist()

    # Main curve
    ax.plot(ts, tmp, color="#ff4b4b", linewidth=2.2, zorder=3)
    ax.scatter(ts, tmp, color="#ff4b4b", s=55, zorder=4)

    # Annotate each point with its value
    for t, v in zip(ts, tmp):
        ax.annotate(
            f"{v:.1f}°",
            (t, v),
            textcoords="offset points", xytext=(4, 6),
            color="white", fontsize=8,
        )

    # Normal fever threshold line
    ax.axhline(37.5, color="#ffd700", linewidth=1.2, linestyle="--", alpha=0.75, label="Fever threshold (37.5°C)")

    # Shade the fever zone
    ax.fill_between(ts, 37.5, tmp, where=[v > 37.5 for v in tmp],
                    color="#ff4b4b", alpha=0.12, label="Fever zone")

    # MAX / MIN annotations from DB stats
    if stats:
        ax.axhline(stats["max_temp"], color="#00c8ff", linewidth=0.9, linestyle=":",
                   alpha=0.7, label=f"MAX {stats['max_temp']}°C")
        ax.axhline(stats["min_temp"], color="#90ee90", linewidth=0.9, linestyle=":",
                   alpha=0.7, label=f"MIN {stats['min_temp']}°C")

    # Pattern label in top-right corner
    if pattern_label:
        ax.text(
            0.98, 0.93, f"Pattern: {pattern_label}",
            transform=ax.transAxes, ha="right", va="top",
            color="white", fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", fc="#ff4b4b", alpha=0.7),
        )

    # Axis styling
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
    fig.autofmt_xdate(rotation=30)
    ax.set_ylabel("Temperature (°C)", color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    ax.yaxis.set_tick_params(color="white")
    ax.legend(fontsize=7.5, facecolor="#1e1e2e", labelcolor="white", loc="lower right")
    ax.grid(True, color="#333", linewidth=0.5, linestyle="--")

    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────
# Helper: Bayesian results display
# ─────────────────────────────────────────────

def _render_bayesian_results(diffs: list, symptoms: list):
    """Render Bayesian differentials as a styled bar chart + colour-coded table."""
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np

    st.markdown("### 🧬 Bayesian Differential Diagnosis")
    st.caption(
        f"P(Disease | Symptoms) ∝ P(Disease) × ∏ P(Symptom|Disease) "
        f"— inputs: *{', '.join(symptoms) if symptoms else 'none'}*"
    )

    diseases = [d["disease"] for d in diffs]
    probs    = [d["probability"] for d in diffs]

    # ── Horizontal bar chart ──────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, max(3, len(diseases) * 0.55)))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    colors = cm.RdYlGn([p for p in probs])
    bars   = ax.barh(diseases[::-1], probs[::-1], color=colors[::-1], height=0.55)

    for bar, p in zip(bars, probs[::-1]):
        ax.text(
            bar.get_width() + 0.008, bar.get_y() + bar.get_height() / 2,
            f"{p*100:.1f}%", va="center", color="white", fontsize=9,
        )

    ax.set_xlim(0, min(max(probs) * 1.25, 1.0))
    ax.set_xlabel("Posterior Probability", color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    ax.grid(True, axis="x", color="#333", linewidth=0.5, linestyle="--")

    st.pyplot(fig)
    plt.close(fig)

    # ── Colour-coded progress bars ────────────────────────────────────────────
    st.markdown("**Ranked probabilities:**")
    for d in diffs:
        p = d["probability"]
        colour = "🔴" if p > 0.4 else "🟠" if p > 0.2 else "🟡" if p > 0.1 else "🟢"
        st.progress(p, text=f"{colour} **{d['disease']}** — {p*100:.1f}%")


# ─────────────────────────────────────────────
# Tab 2 – My Episodes
# ─────────────────────────────────────────────

def _my_episodes_tab():
    st.header("Patient History (Fever Episodes)")
    patient_id = st.text_input("Enter Patient ID to pull history", key="ep_patient_id")

    if st.button("Fetch History"):
        if not patient_id:
            return
        try:
            episodes = _get_patient_episodes(patient_id)

            if not episodes:
                st.info(f"No episodes found for patient {patient_id}.")
                return

            for ep in episodes:
                with st.expander(
                    f"Episode | Pattern: {ep.get('pattern')} | {ep.get('urgency_level')} | "
                    f"Duration: {ep.get('duration_days', 0)}d"
                ):
                    st.write(f"**Duration:** {ep.get('duration_days', 0)} days ({ep.get('duration_category')})")
                    st.write(f"**Symptoms:** {', '.join(ep.get('symptoms', []))}")
                    if ep.get("fuo_risk"):
                        st.warning("⚠️ Flagged as FUO Risk")
                    if ep.get("temp_stats"):
                        ts = ep["temp_stats"]
                        cols = st.columns(4)
                        cols[0].metric("MAX °C", ts.get("max_temp", "—"))
                        cols[1].metric("MIN °C", ts.get("min_temp", "—"))
                        cols[2].metric("Fluctuation", ts.get("fluctuation", "—"))
                        cols[3].metric("Readings", ts.get("reading_count", "—"))
                    diffs = ep.get("differentials", [])
                    if diffs:
                        st.write(f"**Top Prediction:** {diffs[0].get('disease')} ({diffs[0].get('probability', 0)*100:.1f}%)")
        except Exception as e:
            st.error(f"Failed to fetch episodes. {e}")


# ─────────────────────────────────────────────
# Tab 3 – Pattern Analytics
# ─────────────────────────────────────────────

def _analytics_tab():
    st.header("Global Pattern Analytics")
    st.caption("Aggregates data from the `fever_episodes` collection.")
    try:
        stats = _get_pattern_analytics()

        if stats:
            df = pd.DataFrame(stats)
            st.bar_chart(df.set_index("pattern")["count"], color="#1f77b4")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No analytics available yet. Submit an episode first!")
    except Exception as e:
        st.error(f"Failed to fetch analytics. {e}")


# ─────────────────────────────────────────────
# Tab 4 – ER Diagram
# ─────────────────────────────────────────────

def _er_tab():
    st.header("Entity-Relationship Diagram")
    st.caption("Module 8 Data Architecture — MongoDB Collections")
    
    # 1. Get the exact folder path where this patient_view.py file lives
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Join it with the image name
    image_path = os.path.join(current_dir, "ERDiagram.jpeg")
    
    # 3. Pass the absolute path to Streamlit
    try:
        st.image(
            image_path, 
            caption="ER Diagram showing the main collections and their relationships."
        )
    except FileNotFoundError:
        st.error(f"Could not find the image at: {image_path}. Please check the file name!")

    st.markdown("""
| Collection | Role |
|---|---|
| `fever_episodes` | Master document per episode (embedded readings for aggregation) |
| `fuo_guidance` | Lookup / seed collection — FUO workup clinical steps |
| `associated_symptoms` | P(Symptom|Disease) — Bayesian sensitivity weights |
| `differential_diagnoses` | Base P(Disease) — prior prevalence values |
""")


# ─────────────────────────────────────────────
# Tab 5 – DB Schema
# ─────────────────────────────────────────────

def _collections_tab():
    st.header("Database Collections Schema")
    st.write("This module interacts with the following MongoDB collections inside `MedicalCopilotDB`:")

    schema_data = {
        "Collection Name": [
            "fever_episodes",
            "fuo_guidance",
            "associated_symptoms",
            "differential_diagnoses",
        ],
        "Key Fields": [
            "patient_id, temperatures[], pattern, duration_days, fuo_risk, differentials[], temp_stats{}",
            "step_number, category, recommendation",
            "symptom, disease, sensitivity (P(S|D))",
            "disease, base_prevalence (P(D))",
        ],
        "Role in System": [
            "Primary document store; embedded temperatures[] array enables aggregation pipeline.",
            "Seed lookup table: provides FUO workup steps when fuo_risk=True.",
            "Stores Bayesian sensitivity weights used in differential diagnosis.",
            "Stores base disease prevalence (prior probabilities) for Bayesian engine.",
        ],
    }
    st.table(pd.DataFrame(schema_data))

    st.markdown("### `fever_episodes` — Sample Document")
    st.json({
        "patient_id": "PT-123",
        "pattern": "Remittent",
        "duration_days": 5,
        "duration_category": "Acute (<7d)",
        "urgency_level": "Moderate Urgency",
        "fuo_risk": False,
        "symptoms": ["headache", "rigors"],
        "temperatures": [
            {"timestamp": "2026-03-15T08:00:00", "temperature": 37.1},
            {"timestamp": "2026-03-15T12:00:00", "temperature": 39.5},
        ],
        "temp_stats": {
            "max_temp": 39.5,
            "min_temp": 37.1,
            "fluctuation": 2.4,
            "avg_temp": 38.3,
            "reading_count": 2,
            "derived_pattern": "Remittent",
        },
        "differentials": [{"disease": "Typhoid", "probability": 0.72}],
    })


# ─────────────────────────────────────────────
# Tab 6 – FUO & Guidance
# ─────────────────────────────────────────────

def _guidance_tab():
    st.header("Clinical Guidance & Definitions")

    st.subheader("1. Temperature Patterns (DB-classified)")
    st.markdown("""
| Pattern | Condition |
|---|---|
| **No Fever** | MAX < 37.5 °C |
| **Hectic** | Fluctuation ≥ 1.5 °C **and** MAX > 39.0 °C |
| **Continuous** | Fluctuation < 1.0 °C **and** MIN > 37.5 °C |
| **Remittent** | Fluctuation ≥ 1.0 °C **and** MIN > 37.5 °C |
| **Intermittent** | Fluctuation ≥ 1.0 °C **and** MIN ≤ 37.5 °C |
| **Relapsing** | Default (all other cases) |
""")

    st.subheader("2. Duration Categories")
    st.markdown("- **Acute:** < 7 days\n- **Subacute:** 7–21 days\n- **Chronic:** > 21 days")

    st.subheader("3. FUO (Fever of Unknown Origin) Protocol")
    st.info("""
**Classic FUO Criteria:**
1. Temperature > 38.3 °C (101 °F) on several occasions.
2. Duration of fever > 3 weeks (Chronic).
3. Failure to reach a diagnosis despite intensive investigation.
""")


# ─────────────────────────────────────────────
# Tab 7 – Aggregation Query Demo
# ─────────────────────────────────────────────

DEMO_QUERIES = {
    "time_series_stats": {
        "label": "📈 Time-Series Stats (MAX / MIN / AVG / FLUCTUATION)",
        "sql_equivalent": """-- SQL equivalent:
SELECT
    patient_id,
    MAX(temperature)                    AS max_temp,
    MIN(temperature)                    AS min_temp,
    AVG(temperature)                    AS avg_temp,
    COUNT(*)                            AS reading_count,
    MAX(temperature) - MIN(temperature) AS fluctuation
FROM temperature_readings
GROUP BY patient_id
ORDER BY max_temp DESC
LIMIT 10;""",
    },
    "pattern_classification": {
        "label": "🔍 Pattern Classification ($switch = SQL CASE WHEN)",
        "sql_equivalent": """-- SQL equivalent:
SELECT
    patient_id,
    MAX(temperature) AS max_temp,
    MIN(temperature) AS min_temp,
    MAX(temperature) - MIN(temperature) AS fluctuation,
    CASE
        WHEN MAX(temperature) < 37.5 THEN 'No Fever'
        WHEN MAX(temperature) - MIN(temperature) >= 1.5
         AND MAX(temperature) > 39.0             THEN 'Hectic'
        WHEN MAX(temperature) - MIN(temperature) < 1.0
         AND MIN(temperature) > 37.5             THEN 'Continuous'
        WHEN MAX(temperature) - MIN(temperature) >= 1.0
         AND MIN(temperature) > 37.5             THEN 'Remittent'
        WHEN MAX(temperature) - MIN(temperature) >= 1.0
         AND MIN(temperature) <= 37.5            THEN 'Intermittent'
        ELSE 'Relapsing'
    END AS derived_pattern
FROM temperature_readings
GROUP BY patient_id
LIMIT 10;""",
    },
    "fuo_risk_episodes": {
        "label": "🚨 FUO Risk Episodes (WHERE fuo_risk = TRUE)",
        "sql_equivalent": """-- SQL equivalent:
SELECT patient_id, pattern, duration_days, urgency_level, max_temp
FROM fever_episodes
WHERE fuo_risk = TRUE
  AND duration_days > 21
ORDER BY duration_days DESC
LIMIT 10;""",
    },
    "pattern_analytics": {
        "label": "📊 Pattern Analytics (GROUP BY pattern)",
        "sql_equivalent": """-- SQL equivalent:
SELECT
    pattern,
    COUNT(*)              AS episode_count,
    AVG(duration_days)    AS avg_duration_days,
    AVG(max_temp)         AS avg_max_temp,
    SUM(CASE WHEN fuo_risk THEN 1 ELSE 0 END) AS fuo_cases
FROM fever_episodes
GROUP BY pattern
ORDER BY episode_count DESC;""",
    },
    "urgency_breakdown": {
        "label": "⚡ Urgency Breakdown (GROUP BY urgency_level)",
        "sql_equivalent": """-- SQL equivalent:
SELECT
    urgency_level,
    COUNT(*)         AS count,
    AVG(max_temp)    AS avg_peak_temp
FROM fever_episodes
GROUP BY urgency_level
ORDER BY count DESC;""",
    },
}


def _sql_demo_tab():
    st.header("🧪 Aggregation Query Demo")
    st.markdown("""
This tab runs **live MongoDB aggregation pipelines** against your Atlas database.
Each button shows the pipeline definition alongside its **SQL equivalent**, then fetches and renders real results.

> MongoDB's `$unwind → $group → $addFields → $switch` stages are the exact equivalents of SQL's
> `FLATTEN → GROUP BY → computed columns → CASE WHEN`.
""")

    st.divider()

    for query_name, meta in DEMO_QUERIES.items():
        with st.container():
            col_btn, col_info = st.columns([2, 5])
            with col_btn:
                run_it = st.button(meta["label"], key=f"demo_{query_name}", use_container_width=True)
            with col_info:
                st.caption(f"Query: `{query_name}`")

            if run_it:
                with st.spinner(f"Running `{query_name}` aggregation pipeline..."):
                    try:
                        data = _run_sql_demo(query_name)

                        st.success(f"✅ `{query_name}` executed — {len(data['results'])} documents returned.")

                        # SQL Equivalent
                        st.markdown("**SQL Equivalent:**")
                        st.code(meta["sql_equivalent"], language="sql")

                        # MongoDB Pipeline
                        with st.expander("📋 MongoDB Aggregation Pipeline (JSON)", expanded=False):
                            st.json(data["pipeline"])

                        # Results
                        st.markdown("**Live Results from MongoDB:**")
                        if data["results"]:
                            st.dataframe(pd.DataFrame(data["results"]), use_container_width=True)
                        else:
                            st.info("No data in the collection yet — submit a fever episode first.")

                    except requests.exceptions.ConnectionError:
                        st.error(
                            "❌ Cannot connect to the configured FastAPI backend URL. "
                            "Set `FASTAPI_BACKEND_URL` (or `API_BASE_URL`) in Streamlit secrets."
                        )
                    except Exception as e:
                        st.error(f"Error: {e}")

            st.divider()
