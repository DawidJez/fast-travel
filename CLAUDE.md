# Fast Travel

Commute comparison app: save trips (CRUD), compare time / cost / CO2 per transport mode, get a weather-aware recommendation.
One AI feature: free-text trip input -> LLM returns structured JSON -> validated -> prefills the form.

## Working agreement
- Do exactly what is asked, nothing more. No extra features, refactors, dependencies or files that were not requested.
- If a requirement is ambiguous, or a design decision is needed that was not specified, stop and ask before proceeding.
- Never run git commands that change history or the index (`add`, `commit`, `push`, `merge`, `rebase`, `reset`). Version control is handled by the owner.
- Keep changes small and focused. After a change, summarize briefly what was changed and why.

## Stack
- backend/: Python, FastAPI, SQLite (SQLModel/SQLAlchemy), Pydantic, pytest
- frontend/: React + Vite + TypeScript
- External data (no API keys): Open-Meteo geocoding + forecast. LLM provider is hidden behind an `LLMClient` interface.

## Commands
- Backend dev: `cd backend && uvicorn app.main:app --reload`
- Backend tests: `cd backend && pytest`
- Frontend dev: `cd frontend && npm run dev`

## Architecture rules
- Layers: `api/` (routers, HTTP only) -> `services/` (logic) -> models. No business logic in routers.
- Time, cost and CO2 are computed ONLY by deterministic code in `services/`. The LLM never produces numbers.
- All constants (speeds, costs, CO2 g/km, detour factor) live in `app/config.py`, each with a source comment.
- Distance = haversine x detour factor (~1.3). Public transport is an estimate, not real timetables.
- LLM output is always validated with Pydantic; invalid output -> clear error, never a crash.
- Demo mode: the app must run without any API key (stored responses / simple fallback parser).
- Never commit `.env` or database files.

## API (REST)
- `GET/POST /api/trips`, `GET/PUT/DELETE /api/trips/{id}`
- `GET /api/trips/{id}/comparison`
- `POST /api/parse` (AI)
- CORS enabled for the frontend origin.

## Conventions
- Every new function gets a test.
