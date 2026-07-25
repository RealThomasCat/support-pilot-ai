# SupportPilot AI

SupportPilot AI is a work-in-progress backend for an internal customer-support copilot. It provides ticket management, persistent support-agent conversations, Gemini-powered chat, and controlled ticket tool calling.

## Current Features

- FastAPI backend with PostgreSQL persistence
- Ticket create, list, filter, retrieve, and update APIs
- Persistent conversations and ordered message history
- Gemini chat integration
- Registry-based ticket tools with Pydantic argument validation
- Bounded backend-owned tool-calling loop
- Deterministic API and service tests

## Tech Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- Pydantic
- Google Gemini
- Pytest
- Docker Compose

## Local Setup

Start PostgreSQL from the repository root:

```powershell
docker compose up -d postgres
```

Install backend dependencies:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in `backend/.env`, then run migrations:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Run the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

## API Entry Points

- `GET /health`
- `GET /health/db`
- `/tickets`
- `/conversations`
- `/conversations/{conversation_id}/messages`

## Still To Add

- Persisted tool-call logs
- Richer support workflows and reply drafting
- Basic AI eval cases
- Frontend
