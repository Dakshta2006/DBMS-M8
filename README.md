Live Demo: 👉 https://m8-feverbaseddifferentialdiagnosis.streamlit.app/

## Streamlit Cloud Backend Note

On Streamlit Cloud, this app now supports two backend modes:

1. Direct mode (default): Streamlit calls Module B8 backend services in-process.
2. External API mode (optional): Streamlit calls a deployed FastAPI service.

### Why you saw `Cannot connect to FastAPI backend`

That message appears when the app is configured to call an external FastAPI URL but the URL is unreachable.

### How to configure external API mode

In Streamlit Cloud, set one of these secrets:

```toml
FASTAPI_BACKEND_URL = "https://your-fastapi-service.example.com/api/b8"
# or
API_BASE_URL = "https://your-fastapi-service.example.com/api/b8"
```

If neither secret is set, the app automatically uses direct mode and does not require running `uvicorn`.
