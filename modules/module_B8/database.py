# backend/module_B8/database.py
#
# All MongoDB interactions for Module 8 - Fever Evaluation.
# Key feature: classify_temperature_via_aggregation() uses a MongoDB
# aggregation pipeline to compute MAX / MIN / FLUCTUATION / AVG entirely
# inside the database engine — equivalent to a SQL GROUP-BY + Window Function.
#
import motor.motor_asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

# ─────────────────────────────────────────────
# Connection (Atlas)
# ─────────────────────────────────────────────
MONGO_DETAILS = (
    "mongodb+srv://24je0608_db_user:*******"
    "@cluster0.n7xgc4b.mongodb.net/?appName=Cluster0"
)
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
db = client["MedicalCopilotDB"]

# ── Collections ──────────────────────────────
episodes_collection      = db["fever_episodes"]
symptoms_collection      = db["associated_symptoms"]       # P(symptom|disease)
diagnoses_collection     = db["differential_diagnoses"]    # base P(disease)
fuo_guidance_collection  = db["fuo_guidance"]              # FUO workup lookup


# ─────────────────────────────────────────────
# Startup: seed FUO guidance if collection is empty
# ─────────────────────────────────────────────
FUO_GUIDANCE_SEED = [
    {"step_number": 1,  "category": "Lab – Haematology",   "recommendation": "CBC with differential & peripheral smear"},
    {"step_number": 2,  "category": "Lab – Microbiology",  "recommendation": "Blood cultures ×3 (aerobic + anaerobic, drawn 30 min apart)"},
    {"step_number": 3,  "category": "Lab – Microbiology",  "recommendation": "Urine culture + urinalysis (mid-stream clean catch)"},
    {"step_number": 4,  "category": "Lab – Serology",      "recommendation": "ESR, CRP, serum ferritin (inflammation markers)"},
    {"step_number": 5,  "category": "Lab – Serology",      "recommendation": "ANA, ANCA, RF, anti-dsDNA (autoimmune screen)"},
    {"step_number": 6,  "category": "Lab – Serology",      "recommendation": "HIV Ab/Ag combo test, hepatitis B & C serology"},
    {"step_number": 7,  "category": "Lab – Serology",      "recommendation": "Widal / Weil-Felix / Brucella agglutination tests"},
    {"step_number": 8,  "category": "Lab – Biochemistry",  "recommendation": "LFTs, RFTs, LDH, uric acid, protein electrophoresis"},
    {"step_number": 9,  "category": "Imaging",             "recommendation": "Chest X-ray (PA view) — rule out TB, lymphoma"},
    {"step_number": 10, "category": "Imaging",             "recommendation": "Abdominal ultrasound — hepatosplenomegaly, lymph nodes"},
    {"step_number": 11, "category": "Imaging",             "recommendation": "CT Chest-Abdomen-Pelvis with contrast (if USG inconclusive)"},
    {"step_number": 12, "category": "Specialist Referral", "recommendation": "Infectious Disease consult"},
    {"step_number": 13, "category": "Specialist Referral", "recommendation": "Haematology/Oncology consult (rule out lymphoma / leukaemia)"},
    {"step_number": 14, "category": "Specialist Referral", "recommendation": "Rheumatology consult (Still's disease, SLE, vasculitis)"},
]

async def seed_fuo_guidance() -> None:
    """Insert the FUO guidance documents once on startup."""
    if await fuo_guidance_collection.count_documents({}) == 0:
        await fuo_guidance_collection.insert_many(FUO_GUIDANCE_SEED)
        print("[DB] Seeded fuo_guidance collection with", len(FUO_GUIDANCE_SEED), "steps.")


# ─────────────────────────────────────────────
# Seed: P(Symptom | Disease) — associated_symptoms collection
# Each doc: { disease, symptom, sensitivity }
# sensitivity = P(symptom present | patient has disease)
# ─────────────────────────────────────────────
ASSOCIATED_SYMPTOMS_SEED = [
    # ── Typhoid Fever ──
    {"disease": "Typhoid Fever",        "symptom": "headache",         "sensitivity": 0.80},
    {"disease": "Typhoid Fever",        "symptom": "abdominal pain",   "sensitivity": 0.75},
    {"disease": "Typhoid Fever",        "symptom": "constipation",     "sensitivity": 0.60},
    {"disease": "Typhoid Fever",        "symptom": "diarrhea",         "sensitivity": 0.45},
    {"disease": "Typhoid Fever",        "symptom": "rose spots",       "sensitivity": 0.30},
    {"disease": "Typhoid Fever",        "symptom": "rigors",           "sensitivity": 0.50},
    {"disease": "Typhoid Fever",        "symptom": "fatigue",          "sensitivity": 0.85},
    # ── Malaria ──
    {"disease": "Malaria",              "symptom": "rigors",           "sensitivity": 0.92},
    {"disease": "Malaria",              "symptom": "sweating",         "sensitivity": 0.90},
    {"disease": "Malaria",              "symptom": "headache",         "sensitivity": 0.85},
    {"disease": "Malaria",              "symptom": "myalgia",          "sensitivity": 0.78},
    {"disease": "Malaria",              "symptom": "nausea",           "sensitivity": 0.70},
    {"disease": "Malaria",              "symptom": "vomiting",         "sensitivity": 0.65},
    {"disease": "Malaria",              "symptom": "fatigue",          "sensitivity": 0.88},
    {"disease": "Malaria",              "symptom": "splenomegaly",     "sensitivity": 0.60},
    # ── Dengue ──
    {"disease": "Dengue Fever",         "symptom": "headache",         "sensitivity": 0.90},
    {"disease": "Dengue Fever",         "symptom": "retro-orbital pain","sensitivity": 0.75},
    {"disease": "Dengue Fever",         "symptom": "myalgia",          "sensitivity": 0.88},
    {"disease": "Dengue Fever",         "symptom": "rash",             "sensitivity": 0.65},
    {"disease": "Dengue Fever",         "symptom": "nausea",           "sensitivity": 0.70},
    {"disease": "Dengue Fever",         "symptom": "vomiting",         "sensitivity": 0.60},
    {"disease": "Dengue Fever",         "symptom": "joint pain",       "sensitivity": 0.72},
    {"disease": "Dengue Fever",         "symptom": "bleeding gums",    "sensitivity": 0.35},
    # ── Tuberculosis ──
    {"disease": "Tuberculosis",         "symptom": "night sweats",     "sensitivity": 0.85},
    {"disease": "Tuberculosis",         "symptom": "weight loss",      "sensitivity": 0.88},
    {"disease": "Tuberculosis",         "symptom": "cough",            "sensitivity": 0.90},
    {"disease": "Tuberculosis",         "symptom": "haemoptysis",      "sensitivity": 0.40},
    {"disease": "Tuberculosis",         "symptom": "fatigue",          "sensitivity": 0.82},
    {"disease": "Tuberculosis",         "symptom": "chest pain",       "sensitivity": 0.45},
    # ── Infective Endocarditis ──
    {"disease": "Infective Endocarditis","symptom": "rigors",          "sensitivity": 0.70},
    {"disease": "Infective Endocarditis","symptom": "joint pain",      "sensitivity": 0.55},
    {"disease": "Infective Endocarditis","symptom": "sweating",        "sensitivity": 0.65},
    {"disease": "Infective Endocarditis","symptom": "fatigue",         "sensitivity": 0.80},
    {"disease": "Infective Endocarditis","symptom": "chest pain",      "sensitivity": 0.40},
    {"disease": "Infective Endocarditis","symptom": "splinter haemorrhage","sensitivity": 0.25},
    # ── Viral URI / Flu ──
    {"disease": "Influenza",            "symptom": "headache",         "sensitivity": 0.80},
    {"disease": "Influenza",            "symptom": "myalgia",          "sensitivity": 0.90},
    {"disease": "Influenza",            "symptom": "cough",            "sensitivity": 0.85},
    {"disease": "Influenza",            "symptom": "rigors",           "sensitivity": 0.65},
    {"disease": "Influenza",            "symptom": "fatigue",          "sensitivity": 0.90},
    {"disease": "Influenza",            "symptom": "nausea",           "sensitivity": 0.55},
    {"disease": "Influenza",            "symptom": "sore throat",      "sensitivity": 0.70},
    # ── UTI / Pyelonephritis ──
    {"disease": "Pyelonephritis",       "symptom": "rigors",           "sensitivity": 0.75},
    {"disease": "Pyelonephritis",       "symptom": "flank pain",       "sensitivity": 0.88},
    {"disease": "Pyelonephritis",       "symptom": "nausea",           "sensitivity": 0.70},
    {"disease": "Pyelonephritis",       "symptom": "vomiting",         "sensitivity": 0.60},
    {"disease": "Pyelonephritis",       "symptom": "dysuria",          "sensitivity": 0.65},
    {"disease": "Pyelonephritis",       "symptom": "fatigue",          "sensitivity": 0.72},
    # ── Lymphoma ──
    {"disease": "Lymphoma",             "symptom": "night sweats",     "sensitivity": 0.80},
    {"disease": "Lymphoma",             "symptom": "weight loss",      "sensitivity": 0.82},
    {"disease": "Lymphoma",             "symptom": "fatigue",          "sensitivity": 0.85},
    {"disease": "Lymphoma",             "symptom": "itching",          "sensitivity": 0.45},
    {"disease": "Lymphoma",             "symptom": "lymph node swelling","sensitivity": 0.88},
]

# ─────────────────────────────────────────────
# Seed: P(Disease) — base prevalence priors
# base_prevalence = rough estimated population prior (used in Bayesian denominator)
# ─────────────────────────────────────────────
DIFFERENTIAL_DIAGNOSES_SEED = [
    {"disease": "Typhoid Fever",          "base_prevalence": 0.12},
    {"disease": "Malaria",                "base_prevalence": 0.18},
    {"disease": "Dengue Fever",           "base_prevalence": 0.16},
    {"disease": "Tuberculosis",           "base_prevalence": 0.10},
    {"disease": "Infective Endocarditis", "base_prevalence": 0.04},
    {"disease": "Influenza",              "base_prevalence": 0.22},
    {"disease": "Pyelonephritis",         "base_prevalence": 0.10},
    {"disease": "Lymphoma",               "base_prevalence": 0.08},
]


async def seed_bayesian_data() -> None:
    """Seed associated_symptoms and differential_diagnoses if empty."""
    if await symptoms_collection.count_documents({}) == 0:
        await symptoms_collection.insert_many(ASSOCIATED_SYMPTOMS_SEED)
        print("[DB] Seeded associated_symptoms with", len(ASSOCIATED_SYMPTOMS_SEED), "records.")
    if await diagnoses_collection.count_documents({}) == 0:
        await diagnoses_collection.insert_many(DIFFERENTIAL_DIAGNOSES_SEED)
        print("[DB] Seeded differential_diagnoses with", len(DIFFERENTIAL_DIAGNOSES_SEED), "records.")


# ─────────────────────────────────────────────
# Seed: Demo fever_episodes
# Covers all 5 patterns + 2 FUO-qualifying episodes
# so all aggregation demo queries return data immediately.
# ─────────────────────────────────────────────
DEMO_EPISODES_SEED = [
    # ── FUO Episode 1 (Chronic >21d, Remittent, High temp) ──
    {
        "patient_id": "DEMO-001", "pattern": "Remittent",
        "duration_days": 28, "duration_category": "Chronic (>21d)",
        "urgency_level": "High Urgency (Immediate Review)",
        "fuo_risk": True,
        "symptoms": ["rigors", "night sweats", "weight loss", "fatigue"],
        "differentials": [
            {"disease": "Tuberculosis",  "probability": 0.52},
            {"disease": "Lymphoma",      "probability": 0.31},
            {"disease": "Malaria",       "probability": 0.17},
        ],
        "notes": "DEMO: 4-week remittent fever, workup inconclusive.",
        "patient_meta": {"name": "Demo Patient A", "age": 42, "gender": "Male", "comorbidities": None},
        "temperatures": [
            {"timestamp": datetime(2026, 1, 1,  8, 0), "temperature": 37.2},
            {"timestamp": datetime(2026, 1, 1, 20, 0), "temperature": 39.4},
            {"timestamp": datetime(2026, 1, 8,  8, 0), "temperature": 37.4},
            {"timestamp": datetime(2026, 1, 8, 20, 0), "temperature": 39.7},
            {"timestamp": datetime(2026, 1, 15, 8, 0), "temperature": 37.3},
            {"timestamp": datetime(2026, 1, 15,20, 0), "temperature": 38.9},
            {"timestamp": datetime(2026, 1, 29, 8, 0), "temperature": 37.5},
            {"timestamp": datetime(2026, 1, 29,20, 0), "temperature": 39.1},
        ],
        "temp_stats": {
            "max_temp": 39.7, "min_temp": 37.2, "fluctuation": 2.5,
            "avg_temp": 38.44, "reading_count": 8, "derived_pattern": "Remittent"
        },
        "created_at": datetime(2026, 1, 29, 21, 0),
    },
    # ── FUO Episode 2 (Chronic >21d, Continuous, Very high) ──
    {
        "patient_id": "DEMO-002", "pattern": "Continuous",
        "duration_days": 35, "duration_category": "Chronic (>21d)",
        "urgency_level": "High Urgency (Immediate Review)",
        "fuo_risk": True,
        "symptoms": ["fatigue", "weight loss", "night sweats", "lymph node swelling"],
        "differentials": [
            {"disease": "Lymphoma",      "probability": 0.61},
            {"disease": "Tuberculosis",  "probability": 0.28},
            {"disease": "Influenza",     "probability": 0.11},
        ],
        "notes": "DEMO: 5-week continuous high fever, PET and biopsy ordered.",
        "patient_meta": {"name": "Demo Patient B", "age": 55, "gender": "Female", "comorbidities": "Hypertension"},
        "temperatures": [
            {"timestamp": datetime(2026, 2,  1, 8, 0), "temperature": 38.6},
            {"timestamp": datetime(2026, 2,  1,20, 0), "temperature": 38.9},
            {"timestamp": datetime(2026, 2, 15, 8, 0), "temperature": 38.7},
            {"timestamp": datetime(2026, 2, 15,20, 0), "temperature": 39.0},
            {"timestamp": datetime(2026, 3,  7, 8, 0), "temperature": 38.8},
            {"timestamp": datetime(2026, 3,  7,20, 0), "temperature": 38.6},
        ],
        "temp_stats": {
            "max_temp": 39.0, "min_temp": 38.6, "fluctuation": 0.4,
            "avg_temp": 38.77, "reading_count": 6, "derived_pattern": "Continuous"
        },
        "created_at": datetime(2026, 3, 7, 21, 0),
    },
    # ── Hectic Acute Episode (short, high urgency) ──
    {
        "patient_id": "DEMO-003", "pattern": "Hectic",
        "duration_days": 3, "duration_category": "Acute (<7d)",
        "urgency_level": "High Urgency (Immediate Review)",
        "fuo_risk": False,
        "symptoms": ["rigors", "sweating", "headache", "myalgia"],
        "differentials": [
            {"disease": "Malaria",       "probability": 0.68},
            {"disease": "Dengue Fever",  "probability": 0.22},
            {"disease": "Influenza",     "probability": 0.10},
        ],
        "notes": "DEMO: Hectic malaria-pattern fever with rigors.",
        "patient_meta": {"name": "Demo Patient C", "age": 28, "gender": "Male", "comorbidities": None},
        "temperatures": [
            {"timestamp": datetime(2026, 3, 10, 6, 0),  "temperature": 36.8},
            {"timestamp": datetime(2026, 3, 10, 12, 0), "temperature": 40.3},
            {"timestamp": datetime(2026, 3, 10, 18, 0), "temperature": 36.9},
            {"timestamp": datetime(2026, 3, 11,  6, 0), "temperature": 40.6},
            {"timestamp": datetime(2026, 3, 11, 12, 0), "temperature": 37.0},
            {"timestamp": datetime(2026, 3, 13,  6, 0), "temperature": 40.1},
        ],
        "temp_stats": {
            "max_temp": 40.6, "min_temp": 36.8, "fluctuation": 3.8,
            "avg_temp": 38.62, "reading_count": 6, "derived_pattern": "Hectic"
        },
        "created_at": datetime(2026, 3, 13, 14, 0),
    },
    # ── Intermittent Subacute Episode ──
    {
        "patient_id": "DEMO-004", "pattern": "Intermittent",
        "duration_days": 10, "duration_category": "Subacute (7-21d)",
        "urgency_level": "Moderate Urgency",
        "fuo_risk": False,
        "symptoms": ["headache", "sweating", "nausea", "myalgia"],
        "differentials": [
            {"disease": "Dengue Fever",  "probability": 0.55},
            {"disease": "Malaria",       "probability": 0.35},
            {"disease": "Typhoid Fever", "probability": 0.10},
        ],
        "notes": "DEMO: Dengue-like intermittent pattern.",
        "patient_meta": {"name": "Demo Patient D", "age": 22, "gender": "Female", "comorbidities": None},
        "temperatures": [
            {"timestamp": datetime(2026, 3, 5,  8, 0), "temperature": 36.9},
            {"timestamp": datetime(2026, 3, 5, 14, 0), "temperature": 39.2},
            {"timestamp": datetime(2026, 3, 6,  8, 0), "temperature": 36.8},
            {"timestamp": datetime(2026, 3, 6, 14, 0), "temperature": 39.5},
            {"timestamp": datetime(2026, 3, 15, 8, 0), "temperature": 37.0},
        ],
        "temp_stats": {
            "max_temp": 39.5, "min_temp": 36.8, "fluctuation": 2.7,
            "avg_temp": 38.28, "reading_count": 5, "derived_pattern": "Intermittent"
        },
        "created_at": datetime(2026, 3, 15, 16, 0),
    },
    # ── Continuous Routine Episode ──
    {
        "patient_id": "DEMO-005", "pattern": "Continuous",
        "duration_days": 5, "duration_category": "Acute (<7d)",
        "urgency_level": "Moderate Urgency",
        "fuo_risk": False,
        "symptoms": ["cough", "sore throat", "fatigue", "headache"],
        "differentials": [
            {"disease": "Influenza",    "probability": 0.74},
            {"disease": "Tuberculosis", "probability": 0.16},
            {"disease": "Typhoid Fever","probability": 0.10},
        ],
        "notes": "DEMO: Continuous low-grade flu fever.",
        "patient_meta": {"name": "Demo Patient E", "age": 35, "gender": "Male", "comorbidities": None},
        "temperatures": [
            {"timestamp": datetime(2026, 3, 12,  8, 0), "temperature": 38.2},
            {"timestamp": datetime(2026, 3, 12, 20, 0), "temperature": 38.6},
            {"timestamp": datetime(2026, 3, 13,  8, 0), "temperature": 38.4},
            {"timestamp": datetime(2026, 3, 13, 20, 0), "temperature": 38.7},
            {"timestamp": datetime(2026, 3, 17,  8, 0), "temperature": 38.1},
        ],
        "temp_stats": {
            "max_temp": 38.7, "min_temp": 38.1, "fluctuation": 0.6,
            "avg_temp": 38.4, "reading_count": 5, "derived_pattern": "Continuous"
        },
        "created_at": datetime(2026, 3, 17, 10, 0),
    },
    # ── Relapsing Subacute Episode ──
    {
        "patient_id": "DEMO-006", "pattern": "Relapsing",
        "duration_days": 14, "duration_category": "Subacute (7-21d)",
        "urgency_level": "Moderate Urgency",
        "fuo_risk": False,
        "symptoms": ["rigors", "abdominal pain", "fatigue", "constipation"],
        "differentials": [
            {"disease": "Typhoid Fever", "probability": 0.63},
            {"disease": "Malaria",       "probability": 0.24},
            {"disease": "Pyelonephritis","probability": 0.13},
        ],
        "notes": "DEMO: Relapsing typhoid-like pattern.",
        "patient_meta": {"name": "Demo Patient F", "age": 19, "gender": "Female", "comorbidities": None},
        "temperatures": [
            {"timestamp": datetime(2026, 3,  3,  8, 0), "temperature": 39.0},
            {"timestamp": datetime(2026, 3,  4,  8, 0), "temperature": 38.8},
            {"timestamp": datetime(2026, 3,  5,  8, 0), "temperature": 37.1},
            {"timestamp": datetime(2026, 3,  8,  8, 0), "temperature": 39.2},
            {"timestamp": datetime(2026, 3,  9,  8, 0), "temperature": 39.1},
            {"timestamp": datetime(2026, 3, 17,  8, 0), "temperature": 37.2},
        ],
        "temp_stats": {
            "max_temp": 39.2, "min_temp": 37.1, "fluctuation": 2.1,
            "avg_temp": 38.57, "reading_count": 6, "derived_pattern": "Relapsing"
        },
        "created_at": datetime(2026, 3, 17, 12, 0),
    },
]


async def seed_demo_episodes() -> None:
    """Insert demo episodes once so all aggregation queries return data immediately."""
    if await episodes_collection.count_documents({"patient_id": {"$regex": "^DEMO-"}}) == 0:
        await episodes_collection.insert_many(DEMO_EPISODES_SEED)
        print("[DB] Seeded", len(DEMO_EPISODES_SEED), "demo fever episodes.")


async def seed_all_collections() -> None:
    """Master seed function — called once on FastAPI startup."""
    await seed_fuo_guidance()
    await seed_bayesian_data()
    await seed_demo_episodes()



# ─────────────────────────────────────────────
# Core AGGREGATION — Time-Series Pattern Classification
#
# This MongoDB aggregation pipeline is the equivalent of the SQL:
#
#   SELECT
#     MAX(temperature)                AS max_temp,
#     MIN(temperature)                AS min_temp,
#     MAX(temperature)-MIN(temperature) AS fluctuation,
#     AVG(temperature)                AS avg_temp,
#     COUNT(*)                        AS reading_count
#   FROM temperature_readings
#   WHERE episode_id = :id
#   GROUP BY episode_id;
#
# MongoDB stores the readings as an embedded array inside each
# fever_episode document, so $unwind + $group achieves the same
# relational aggregation semantics.
# ─────────────────────────────────────────────

TEMP_STATS_PIPELINE = [
    # Stage 1 – Flatten the embedded temperatures array into individual docs
    {"$unwind": "$temperatures"},

    # Stage 2 – GROUP BY episode_id (aggregation equivalent of SQL GROUP BY)
    {"$group": {
        "_id": "$_id",
        "patient_id":    {"$first": "$patient_id"},
        "max_temp":      {"$max": "$temperatures.temperature"},   # MAX()
        "min_temp":      {"$min": "$temperatures.temperature"},   # MIN()
        "avg_temp":      {"$avg": "$temperatures.temperature"},   # AVG()
        "reading_count": {"$sum": 1},                             # COUNT(*)
    }},

    # Stage 3 – Compute fluctuation = MAX - MIN  (derived field, like SQL expression)
    {"$addFields": {
        "fluctuation": {"$subtract": ["$max_temp", "$min_temp"]}
    }},

    # Stage 4 – Apply the 5-pattern classification logic as a $switch expression
    {"$addFields": {
        "derived_pattern": {
            "$switch": {
                "branches": [
                    {"case": {"$lt":  ["$max_temp", 37.5]},
                     "then": "No Fever"},
                    {"case": {"$and": [{"$gte": ["$fluctuation", 1.5]},
                                       {"$gt":  ["$max_temp", 39.0]}]},
                     "then": "Hectic"},
                    {"case": {"$and": [{"$lt":  ["$fluctuation", 1.0]},
                                       {"$gt":  ["$min_temp", 37.5]}]},
                     "then": "Continuous"},
                    {"case": {"$and": [{"$gte": ["$fluctuation", 1.0]},
                                       {"$gt":  ["$min_temp", 37.5]}]},
                     "then": "Remittent"},
                    {"case": {"$and": [{"$gte": ["$fluctuation", 1.0]},
                                       {"$lte": ["$min_temp", 37.5]}]},
                     "then": "Intermittent"},
                ],
                "default": "Relapsing"
            }
        }
    }},
]


async def classify_temperature_via_aggregation(episode_id: str) -> Dict[str, Any]:
    """
    Runs the TEMP_STATS_PIPELINE against the just-saved episode document.
    Returns max_temp, min_temp, fluctuation, avg_temp, reading_count,
    and the DB-derived pattern — all computed inside MongoDB.
    """
    from bson import ObjectId
    pipeline = [{"$match": {"_id": ObjectId(episode_id)}}] + TEMP_STATS_PIPELINE
    cursor = episodes_collection.aggregate(pipeline)
    results = await cursor.to_list(length=1)
    if not results:
        return {}
    r = results[0]
    return {
        "max_temp":       round(r["max_temp"], 2),
        "min_temp":       round(r["min_temp"], 2),
        "fluctuation":    round(r["fluctuation"], 2),
        "avg_temp":       round(r["avg_temp"], 2),
        "reading_count":  r["reading_count"],
        "derived_pattern": r["derived_pattern"],
    }


# ─────────────────────────────────────────────
# CRUD helpers
# ─────────────────────────────────────────────

async def fetch_symptom_weights(symptoms: List[str]) -> List[Dict[str, Any]]:
    """Fetches P(Symptom|Disease) sensitivity weights from associated_symptoms."""
    cursor = symptoms_collection.find({"symptom": {"$in": symptoms}})
    return await cursor.to_list(length=1000)


async def fetch_disease_prevalence() -> Dict[str, float]:
    """Fetches base P(Disease) from differential_diagnoses."""
    cursor = diagnoses_collection.find({})
    results = await cursor.to_list(length=100)
    return {doc["disease"]: doc.get("base_prevalence", 0.01) for doc in results}


async def save_fever_episode(episode_data: Dict[str, Any]) -> str:
    """Inserts a new fever episode document and returns its string _id."""
    episode_data["created_at"] = datetime.utcnow()
    result = await episodes_collection.insert_one(episode_data)
    return str(result.inserted_id)


async def update_episode_pattern(episode_id: str, pattern: str, stats: Dict[str, Any]) -> None:
    """After DB-level aggregation, persist the computed pattern back onto the document."""
    from bson import ObjectId
    await episodes_collection.update_one(
        {"_id": ObjectId(episode_id)},
        {"$set": {"pattern": pattern, "temp_stats": stats}}
    )


async def fetch_patient_episodes(patient_id: str) -> List[Dict[str, Any]]:
    cursor = episodes_collection.find({"patient_id": patient_id}).sort("created_at", -1)
    episodes = await cursor.to_list(length=50)
    for ep in episodes:
        ep["_id"] = str(ep["_id"])
    return episodes


async def fetch_pattern_analytics() -> List[Dict[str, Any]]:
    """
    Advanced analytics aggregation — equivalent SQL:
      SELECT pattern, COUNT(*) as count,
             AVG(duration_days) as avg_duration,
             AVG(max_temp_stat) as avg_max_temp,
             SUM(CASE WHEN fuo_risk THEN 1 ELSE 0 END) as fuo_count
      FROM fever_episodes GROUP BY pattern ORDER BY count DESC;
    """
    pipeline = [
        {"$group": {
            "_id":                  "$pattern",
            "count":                {"$sum": 1},
            "average_duration_days":{"$avg": "$duration_days"},
            "avg_max_temp":         {"$avg": "$temp_stats.max_temp"},
            "fuo_count":            {"$sum": {"$cond": ["$fuo_risk", 1, 0]}},
        }},
        {"$sort": {"count": -1}},
    ]
    cursor = episodes_collection.aggregate(pipeline)
    results = await cursor.to_list(length=20)
    return [
        {
            "pattern":               r["_id"] or "Unknown",
            "count":                 r["count"],
            "average_duration_days": r.get("average_duration_days"),
            "avg_max_temp":          round(r["avg_max_temp"], 2) if r.get("avg_max_temp") else None,
            "fuo_count":             r.get("fuo_count", 0),
        }
        for r in results
    ]


async def fetch_fuo_guidance() -> List[Dict[str, Any]]:
    """Returns the full ordered FUO workup checklist from the lookup collection."""
    cursor = fuo_guidance_collection.find({}, {"_id": 0}).sort("step_number", 1)
    return await cursor.to_list(length=50)


# ─────────────────────────────────────────────
# SQL-Demo Query Registry
# (Named aggregation pipelines exposed via the /sql-demo API endpoint)
# ─────────────────────────────────────────────

SQL_DEMO_QUERIES: Dict[str, Dict[str, Any]] = {
    "time_series_stats": {
        "description": (
            "Aggregation pipeline that computes MAX, MIN, AVG, "
            "and FLUCTUATION of temperature readings per episode — "
            "equivalent to a SQL GROUP BY with aggregate functions."
        ),
        "pipeline": [
            {"$unwind": "$temperatures"},
            {"$group": {
                "_id": "$patient_id",
                "max_temp":      {"$max": "$temperatures.temperature"},
                "min_temp":      {"$min": "$temperatures.temperature"},
                "avg_temp":      {"$avg": "$temperatures.temperature"},
                "reading_count": {"$sum": 1},
            }},
            {"$addFields": {"fluctuation": {"$subtract": ["$max_temp", "$min_temp"]}}},
            {"$sort": {"max_temp": -1}},
            {"$limit": 10},
        ],
    },
    "pattern_classification": {
        "description": (
            "Full time-series classification pipeline: $unwind + $group (aggregation) "
            "followed by $switch expressions for 5-pattern detection — "
            "equivalent to a SQL CASE WHEN … END inside a GROUP BY query."
        ),
        "pipeline": TEMP_STATS_PIPELINE + [{"$limit": 10}],
    },
    "fuo_risk_episodes": {
        "description": (
            "Filters episodes where fuo_risk=true and duration>21 days, "
            "projecting key clinical fields — equivalent to SQL WHERE fuo_risk=TRUE."
        ),
        "pipeline": [
            {"$match": {"fuo_risk": True, "duration_days": {"$gt": 21}}},
            {"$project": {
                "_id": 0,
                "patient_id": 1,
                "pattern": 1,
                "duration_days": 1,
                "urgency_level": 1,
                "temp_stats.max_temp": 1,
            }},
            {"$sort": {"duration_days": -1}},
            {"$limit": 10},
        ],
    },
    "pattern_analytics": {
        "description": (
            "GROUP BY pattern with COUNT, AVG duration, AVG max temp, and FUO count — "
            "mirrors a multi-aggregate SQL GROUP BY query."
        ),
        "pipeline": [
            {"$group": {
                "_id":                   "$pattern",
                "episode_count":         {"$sum": 1},
                "avg_duration_days":     {"$avg": "$duration_days"},
                "avg_max_temp":          {"$avg": "$temp_stats.max_temp"},
                "fuo_cases":             {"$sum": {"$cond": ["$fuo_risk", 1, 0]}},
            }},
            {"$sort": {"episode_count": -1}},
        ],
    },
    "urgency_breakdown": {
        "description": (
            "Counts episodes per urgency level and computes average peak temperature — "
            "a SQL GROUP BY urgency_level with COUNT and AVG."
        ),
        "pipeline": [
            {"$group": {
                "_id":           "$urgency_level",
                "count":         {"$sum": 1},
                "avg_peak_temp": {"$avg": "$temp_stats.max_temp"},
            }},
            {"$sort": {"count": -1}},
        ],
    },
}


async def run_sql_demo(query_name: str) -> Optional[Dict[str, Any]]:
    """Execute a named demo aggregation pipeline and return results."""
    q = SQL_DEMO_QUERIES.get(query_name)
    if not q:
        return None
    cursor = episodes_collection.aggregate(q["pipeline"])
    results = await cursor.to_list(length=20)
    # Stringify ObjectId fields
    for r in results:
        if "_id" in r:
            r["_id"] = str(r["_id"])
    return {
        "query_name":  query_name,
        "description": q["description"],
        "pipeline":    q["pipeline"],
        "results":     results,
    }