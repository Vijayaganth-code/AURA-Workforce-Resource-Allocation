# AURA — AI Workforce Decision & Resource Allocation Agent

## Overview

AURA is a local hackathon application for workforce planning. It keeps workforce and task data in SQLite, predicts completion time and SLA breach probability with saved Random Forest models, generates qualified candidates, uses OR-Tools CP-SAT to select an allocation, and requires a manager approval before changing assignments.

**ML predicts. OR-Tools optimizes. AURA explains. The manager decides.**

## Architecture

`Browser dashboard → FastAPI → SQLite → feature pipeline → Random Forest models → candidate filtering → OR-Tools CP-SAT → pending recommendation → approval transaction`

The database is the source of truth. It contains 50 deterministic employees, 20 skills, 100 tasks, multi-person-capable assignments, task requirements, and 1,000 historical performance records. Schema tables are: `employees`, `skills`, `employee_skills`, `tasks`, `task_requirements`, `assignments`, `performance_history`, `leave_requests`, `break_sessions`, `events`, `simulation_runs`, `notifications`, and `recommendations`.

## ML models

At startup, AURA loads saved `.joblib` models or trains them once if absent. The feature pipeline varies workload, skill match, skill level, experience, historical completion, SLA success, estimated/remaining hours, complexity, priority, deadline pressure, and performance.

- Completion Time: `RandomForestRegressor`; reports MAE, RMSE, R².
- SLA Risk: `RandomForestClassifier`; reports accuracy, precision, recall, F1, ROC-AUC.

Metrics are exposed at `GET /api/ml/metrics`. The dataset is synthetic and is strictly a hackathon demonstration model, not production validation.

## API highlights

- `GET /api/dashboard`, `/api/employees`, `/api/tasks`, `/api/sla-risk`
- `GET /api/tasks/{task_id}/candidates` and `/recommendation`
- `POST /api/ml/predict-completion`, `/api/ml/predict-sla-risk`
- `POST /api/reallocate` → creates a pending recommendation
- `POST /api/recommendations/{id}/approve` → performs the assignment transaction
- `POST /api/break/start`, `/api/break/end`, `/api/leave/analyze`, `/api/employee/unavailable`, `/api/incidents`, `/api/simulate`
- `POST /api/demo/reset` restores deterministic demo data

## Install and run

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). First start creates `aura.db` and model artifacts under `ml/models/`.

To train/load models manually:

```powershell
python -m ml.train_completion_model
python -m ml.train_sla_model
```

Copy `.env.example` to `.env` only if adding optional external services. No secret is exposed to browser code.

## Hackathon demo

1. Open Command Center: the displayed employees, tasks, utilization and risks come from `/api/dashboard`.
2. Select a critical/high-priority task; its decision card loads candidate predictions and an OR-Tools recommendation.
3. Run a scenario. It clones the workforce state and returns before/after candidate and SLA results without updating the database.
4. Click Request approval. A pending recommendation is created, then approved transactionally.
5. Call `POST /api/break/start` with an employee ID to demonstrate a database-backed status change; `/api/break/end` restores availability.
6. Call `POST /api/leave/analyze` to demonstrate a non-mutating leave simulation.
7. Ask the Analyst about risk or leave. It is labeled as a local data-backed fallback unless an LLM integration is configured.
8. Call `POST /api/demo/reset` to restore the initial dataset.

## Limitations and future work

This project uses synthetic data, local SQLite, polling/API refresh rather than realtime sockets, and a local data-backed chat fallback. Production rollout requires identity/authentication, PostgreSQL migrations, external model monitoring, richer calendar/leave rules, audit access controls, and validation on real operational data.
