# WorkforceOS AI — Combined & Hardened Dashboard

**ML predicts. OR-Tools optimizes. AURA explains. The manager decides.**

This is the merged version of the original WorkforceOS prototype and the AURA debugged backend, with a hardened, error-resilient frontend.

## Architecture

```
Browser (index.html + app.js)
  ↕  graceful fallback to local demo if API is offline
FastAPI (main.py)
  ↕
SQLite (aura.db)  →  Feature pipeline  →  Random Forest models  →  OR-Tools CP-SAT
                                                                   ↓
                                            Pending recommendation → Manager approves
```

## Key improvements in this build

### Frontend (app.js / index.html)
- **Graceful offline fallback** — every API call is wrapped with a timeout and try/catch; the full dashboard still renders with local demo data if FastAPI is not running.
- **Sign-out fixed** — the profile avatar and the "Sign out" text button both clear the session and return to `employee.html`.
- **API status dot** — live (green) / offline (amber) indicator in the topbar updates after each load.
- **Demo-reset button** — appears in the status strip only when the API is live; calls `POST /api/demo/reset` and reloads the page.
- **Live task table** — uses real `task_name`, `department`, `remaining_hours`, and ML-derived `sla_breach_probability` when API is live; falls back to static rows otherwise.
- **Live decision panel** — fetches `GET /api/tasks/{id}/recommendation` on tab change; renders OR-Tools factors with real scores. Falls back per-tab if the recommendation endpoint fails.
- **Live roster** — directory and analytics views render from `GET /api/employees`; fallback uses the same 48-employee local array as before.
- **Live notifications** — fetches `GET /api/notifications`; falls back to static alerts.
- **Simulation** — sends real payloads to `POST /api/simulate`; fallback shows deterministic results.
- **Analyst chat** — calls `POST /api/agent/chat`; fallback uses keyword matching.
- **Approval flow** — `POST /api/reallocate` then `POST /api/recommendations/{id}/approve`; local approval just decrements the risk counter.

### Backend (main.py / services.py / backend_database.py)
- Full AURA backend from the debugged build: 50 employees, 100 tasks, 1 000 performance history records, seeded deterministically (random seed 42).
- ML models: `RandomForestRegressor` (completion time) + `RandomForestClassifier` (SLA breach probability). Models are loaded from `ml/models/*.joblib` at startup, or trained once if absent.
- OR-Tools CP-SAT allocation optimizer with deterministic fallback sort.
- `POST /api/demo/reset` restores the original dataset from scratch.
- `GET /api/ml/metrics` exposes model evaluation metrics.
- Full break, leave, and incident workflow endpoints.

## Run (full dynamic mode)

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open **http://127.0.0.1:8000**

First start creates `aura.db` and trains models into `ml/models/` (takes ~10 s). Subsequent starts load the saved models instantly.

## Run (static preview, no Python needed)

```bash
node serve.js
```

Open **http://127.0.0.1:8000** — renders with local demo data, no API calls succeed.

## Login

- **Manager dashboard**: `manager.demo@workforceos.local` → select *Manager* on the login screen.
- **Employee portals**: any of the email addresses shown in the "View local demo accounts" section.

## API highlights

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard` | Tasks, metrics, SLA radar |
| GET | `/api/employees` | Full employee list |
| GET | `/api/tasks/{id}/recommendation` | OR-Tools recommendation for a task |
| POST | `/api/reallocate` | Create a pending recommendation |
| POST | `/api/recommendations/{id}/approve` | Manager approval transaction |
| POST | `/api/simulate` | Non-mutating what-if scenario |
| POST | `/api/agent/chat?question=…` | Workforce analyst |
| POST | `/api/break/start` · `/api/break/end` | Break session management |
| POST | `/api/leave/analyze` · `/api/leave/request` | Leave workflow |
| GET | `/api/ml/metrics` | Model evaluation metrics |
| POST | `/api/demo/reset` | Restore deterministic seed data |

## Prototype boundary

All recommendations require explicit manager approval before assignments change. Synthetic data only. No real employee data is used or stored.
