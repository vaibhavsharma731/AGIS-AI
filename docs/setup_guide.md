# AegisAI — Setup & How-to-Run Guide

## Quick Start (3 Simple Steps)

### Step 1: Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### Step 2: (Optional) Set your LLM API Key
Open `.env` in the root folder:
```env
LLM_PROVIDER=google
GOOGLE_API_KEY=your_gemini_api_key_here
```
> Note: AegisAI includes a built-in structured analyzer fallback, so it works out of the box even without an API key!

### Step 3: Launch AegisAI Server & Dashboard
```powershell
.\venv\Scripts\python.exe -m backend.app.main
```

Then open your browser and navigate to:
👉 **[http://localhost:8000/dashboard/](http://localhost:8000/dashboard/)**

---

## Running Automated Tests

To test the LangGraph state machine, RAG retrieval, and Human-in-the-Loop workflow:

```powershell
.\venv\Scripts\python.exe -m backend.tests.test_workflow
```

---

## Simulating Different Incident Scenarios

You can switch incident scenarios using `fake_scripts/simulate_incident.py`:

- **Database Connection Exhaustion**:
  ```powershell
  .\venv\Scripts\python.exe fake_scripts/simulate_incident.py db_exhaustion
  ```

- **Memory Leak / OOM Crash**:
  ```powershell
  .\venv\Scripts\python.exe fake_scripts/simulate_incident.py memory_leak
  ```
