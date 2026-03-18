# Module 8 - Fever Evaluation & Differential Diagnosis

## Overview

**Module 8** is a comprehensive fever evaluation and differential diagnosis system built for the Medical Copilot platform. It provides intelligent triage, Bayesian-based diagnosis, and FUO (Fever of Unknown Origin) guidance using MongoDB aggregation pipelines and advanced pattern recognition.

## Features

### 1. **Fever Episode Management**
- Submit and track fever episodes with comprehensive patient data
- Automatic database aggregation for temperature statistics (MAX, MIN, AVERAGE, FLUCTUATION)
- Real-time pattern classification (Continuous, Remittent, Intermittent, Hectic)
- Episode duration categorization (Acute, Subacute, Chronic)

### 2. **Intelligent Triage System**
- **Urgency Classification**:
  - High Urgency: Temp ≥40°C or Hectic pattern
  - Moderate Urgency: Temp ≥38.5°C
  - Routine: All other cases
- Rapid assessment for clinical decision-making

### 3. **Bayesian Differential Diagnosis Engine**
- Implements Bayes' Theorem: `P(Disease|Symptoms) = P(Symptoms|Disease) × P(Disease) / P(Symptoms)`
- Symptom-disease probability mapping
- Disease prevalence-based prior calculations
- Returns ranked differential diagnoses with confidence scores

### 4. **FUO (Fever of Unknown Origin) Guidance**
- **14-step diagnostic workup**:
  - Haematology labs (CBC, peripheral smear)
  - Blood cultures (aerobic + anaerobic)
  - Serology tests (ANA, ANCA, RF, HIV, Hepatitis)
  - Advanced imaging (CXR, Abdominal USG, CT CAP)
  - Specialist referral recommendations

### 5. **Pattern Analytics**
- Aggregate statistics by fever pattern
- Calculate average duration and temperature ranges per pattern
- Support for trend analysis and epidemiological studies

---

## Project Structure

```
module_B8/
├── __init__.py              # Package initialization
├── README.md                # This file
├── api.py                   # FastAPI endpoints & routing
├── database.py              # MongoDB operations & aggregation pipelines
├── services.py              # Business logic & Bayesian engine
├── schemas.py               # Pydantic data models
└── __pycache__/             # Python cache (ignored in git)
```

---

## API Endpoints

### Core Endpoints

#### **1. Create Fever Episode**
```
POST /api/b8/episodes
Content-Type: application/json
```

**Request Body:**
```json
{
  "patient_id": "P12345",
  "temperature_readings": [38.5, 39.2, 39.8, 38.9],
  "symptoms": ["cough", "headache", "fatigue"],
  "onset_date": "2024-03-15",
  "additional_notes": "Started suddenly after exposure"
}
```

**Response (201 Created):**
```json
{
  "episode_id": "EP67890",
  "patient_id": "P12345",
  "pattern": "Remittent",
  "max_temperature": 39.8,
  "min_temperature": 38.5,
  "average_temperature": 39.1,
  "fluctuation": 1.3,
  "duration_category": "Acute (<7d)",
  "urgency_level": "Moderate Urgency",
  "differential_diagnosis": [
    {
      "disease": "Influenza",
      "probability": 0.65,
      "confidence": "High"
    },
    {
      "disease": "Pneumonia",
      "probability": 0.25,
      "confidence": "Moderate"
    }
  ],
  "fuo_guidance": [...],
  "created_at": "2024-03-15T10:30:00Z"
}
```

#### **2. Get Patient Episodes**
```
GET /api/b8/episodes/{patient_id}
```

**Response:**
```json
{
  "patient_id": "P12345",
  "episodes": [
    {
      "episode_id": "EP67890",
      "pattern": "Remittent",
      "max_temperature": 39.8,
      "date": "2024-03-15"
    }
  ]
}
```

#### **3. Get Pattern Analytics**
```
GET /api/b8/analytics/patterns
```

**Response:**
```json
[
  {
    "pattern": "Continuous",
    "count": 12,
    "avg_duration_days": 5.3,
    "avg_max_temp": 39.1
  },
  {
    "pattern": "Remittent",
    "count": 8,
    "avg_duration_days": 4.7,
    "avg_max_temp": 39.4
  }
]
```

---

## Data Models (Schemas)

### FeverEpisodeCreate
Input schema for creating a fever episode:
- `patient_id` (str): Unique patient identifier
- `temperature_readings` (List[float]): Temperature measurements
- `symptoms` (List[str]): Associated symptoms
- `onset_date` (date): When fever started
- `duration_days` (int): Fever duration in days

### FeverEpisodeResponse
Output schema with full analysis:
- All input fields plus:
- `pattern` (str): Classified fever pattern
- `max_temperature`, `min_temperature`, `average_temperature` (float): Statistics
- `fluctuation` (float): Temperature variance
- `urgency_level` (str): Triage classification
- `differential_diagnosis` (List[Dict]): Bayesian results
- `fuo_guidance` (List[Dict]): If applicable

---

## Database Collections

### fever_episodes
```json
{
  "_id": ObjectId,
  "patient_id": String,
  "temperatures": [Float],
  "symptoms": [String],
  "pattern": String,
  "max_temp": Float,
  "min_temp": Float,
  "avg_temp": Float,
  "fluctuation": Float,
  "urgency": String,
  "created_at": Date,
  "updated_at": Date
}
```

### associated_symptoms
```json
{
  "_id": ObjectId,
  "disease": String,
  "symptom": String,
  "probability": Float  // P(Symptom|Disease)
}
```

### differential_diagnoses
```json
{
  "_id": ObjectId,
  "disease": String,
  "base_prevalence": Float  // P(Disease)
}
```

### fuo_guidance
```json
{
  "step_number": Integer,
  "category": String,
  "recommendation": String
}
```

---

## Fever Pattern Classification

Module 8 classifies fever into **4 clinical patterns**:

| Pattern | Description | Example | Clinical Significance |
|---------|-------------|---------|-----------------------|
| **Continuous** | Fluctuation < 1°C, stays elevated | ~39.5°C constant | Pneumonia, Typhoid (early) |
| **Remittent** | Fluctuates 1-2°C daily, never normal | 38-39.5°C swings | Bacterial infection, TB |
| **Intermittent** | Rises to peak, falls to normal daily | Spikes daily | Malaria, abscesses |
| **Hectic** | Wild swings ≥2°C | 37-40°C hourly | Sepsis, endocarditis |

---

## Urgency Triage Algorithm

```python
if max_temp >= 40.0 OR pattern == "Hectic":
    urgency = "High Urgency (Immediate Review)"
elif max_temp >= 38.5:
    urgency = "Moderate Urgency"
else:
    urgency = "Routine"
```

---

## Duration Categories

- **Acute**: < 7 days
- **Subacute**: 7-21 days
- **Chronic**: > 21 days

---

## Key Technologies

- **Backend**: FastAPI (Python)
- **Database**: MongoDB with AsyncIO Motor driver
- **Aggregation**: MongoDB aggregation pipelines for real-time statistics
- **Data Validation**: Pydantic schemas
- **Async/Await**: Non-blocking database operations
- **Statistics**: Bayesian probability calculations

---

## Installation & Setup

### 1. Install Dependencies
```bash
pip install fastapi motor pydantic pymongo
```

### 2. Configure MongoDB
Update connection string in `database.py`:
```python
MONGO_DETAILS = "mongodb+srv://username:password@your-cluster.mongodb.net/?appName=MedicalCopilot"
```

### 3. Initialize Collections
Run seed function on application startup:
```python
await seed_fuo_guidance()
```

### 4. Include Router in Main App
In your FastAPI main application:
```python
from modules.module_B8.api import router as b8_router
app.include_router(b8_router)
```

---

## Usage Examples

### Python/FastAPI Client

```python
import httpx

# Create fever episode
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/b8/episodes",
        json={
            "patient_id": "P12345",
            "temperature_readings": [38.5, 39.2, 39.8],
            "symptoms": ["cough", "headache"],
            "onset_date": "2024-03-15",
            "duration_days": 3
        }
    )
    episode = response.json()
    print(f"Episode ID: {episode['episode_id']}")
    print(f"Diagnosis: {episode['differential_diagnosis'][0]['disease']}")
```

### cURL

```bash
curl -X POST http://localhost:8000/api/b8/episodes \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "P12345",
    "temperature_readings": [38.5, 39.2, 39.8],
    "symptoms": ["cough", "headache"],
    "onset_date": "2024-03-15",
    "duration_days": 3
  }'
```

---

## Error Handling

| Status Code | Scenario |
|-------------|----------|
| 201 | Episode created successfully |
| 400 | Invalid input data |
| 404 | Patient/Episode not found |
| 500 | Server error (check logs) |

---

## Performance Notes

- **Aggregation Pipeline**: Runs entirely in MongoDB engine (~50ms for 1000 recordings)
- **Bayesian Calculation**: O(n×m) where n=symptoms, m=diseases (~10-20ms)
- **Async Operations**: Non-blocking; can handle 100s of concurrent requests

---

## Future Enhancements

- [ ] Machine learning model refinement with historical data
- [ ] Integration with external medical knowledge bases
- [ ] Real-time monitoring dashboard
- [ ] Mobile app support
- [ ] Advanced time-series forecasting
- [ ] Integration with EHR systems

---

## Contributors

- Medical Copilot Development Team
- Database: M8-Fever Based Differential Diagnosis

---

## References

- Bayesian Differential Diagnosis: [Medical Literature]
- Fever Pattern Classification: [Clinical Guidelines]
- FUO Workup Protocol: [Harrison's Principles of Internal Medicine]

---

## License

Medical Copilot System - Internal Use Only

**Last Updated**: March 2024
