# AGENTS.md

Context for coding agents working on this repo.

## What this is

Web app for sketching simplified floor layouts and **estimating** evacuation times.
Results are estimates only — **not** safety certification or regulatory compliance.

## Stack and how to run

| Layer | Stack | Location |
|-------|--------|----------|
| Backend | FastAPI, Pydantic 2, SQLAlchemy 2, SQLite | `backend/` |
| Frontend | React 19, TypeScript, Vite, Konva | `frontend/` |

- Backend must be started from **`backend/`** so relative SQLite (`./data/`) and `.env` resolve correctly:
  `uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm run dev` → http://localhost:5173
- OpenAPI: http://localhost:8000/docs
- Full setup: see [README.md](README.md)

## Architecture

```text
API routers → services → domain / simulation engine
                ↓
         SQLite (JSON columns for layout, params, results, frames)
```

- **ORM models** (`backend/app/models/`) are thin persistence; business types live in Pydantic domain models.
- **Frontend types** mirror the backend domain; keep them in sync when schemas change.
- Simulation runs **synchronously** on the server; the full frame timeline is returned in one response (no WebSockets).

## Where to change what

| Concern | Path |
|---------|------|
| Domain types (layout, params, frames, results) | `backend/app/domain/building.py` |
| API request/response schemas | `backend/app/schemas/api.py` |
| Building / simulation HTTP routes | `backend/app/api/buildings.py`, `simulations.py` |
| Persistence + seed | `backend/app/services/`, `backend/app/services/seed.py` |
| Discrete-time loop | `backend/app/simulation/engine.py` |
| Nav graph | `backend/app/simulation/graph.py` |
| Route choice (Dijkstra) | `backend/app/simulation/routing.py` |
| Capacity / queues | `backend/app/simulation/flow.py` |
| Spatial collision / apertures / space edges | `backend/app/simulation/collision.py` |
| Occupant spatial movement | `backend/app/simulation/movement.py` |
| Stats / hotspots | `backend/app/simulation/results.py` |
| TS domain mirrors | `frontend/src/types/building.ts` |
| REST client | `frontend/src/services/api.ts` |
| Editor canvas | `frontend/src/components/BuildingCanvas.tsx` |
| Playback | `frontend/src/simulation/useSimulationPlayback.ts` |
| App wiring (save / run / playback) | `frontend/src/App.tsx` |

## Domain invariants

- Layout pieces: **spaces** (`room` \| `corridor` \| `stairs`), **doors**, **exits**, **occupant_groups**.
- Connectivity is **doors + exits only** on the nav graph. Space rectangle edges act as solid barriers for movement (door/exit widths are the only gaps). Space edges do not cut the navigation graph.
- Occupant groups expand to individuals; each gets a **fixed route at spawn** (no replanning).
- Occupants steer in continuous `(x, y)` toward waypoints with body radius collisions against people and space-edge solids; door/exit **width** limits concurrent passage (`floor(width / (2 * radius))`).
- Soft validation on **save** (incomplete layouts OK). Hard validation on **run** (need spaces, exits, occupant groups).
- Creating a simulation **snapshots** the building layout; later edits do not change that sim (UI creates a new sim on Run).

## Sync and extension rules

- When changing domain shapes, update **both** `backend/app/domain/building.py` and `frontend/src/types/building.ts` (and API schemas if exposed).
- Prefer swapping behaviour via protocols already used by the engine: `RouteSelector`, `FlowModel`, `SpatialMovementModel` — do not hard-wire a new model into the loop unless necessary.
- Keep layering: do not put simulation logic in API routers or ORM models.

## Gotchas

- Run uvicorn with CWD = `backend/` (or set `DATABASE_URL` / env paths accordingly). Root `.env` may not load if CWD is wrong.
- Large occupant counts + fine timesteps → large `frames_json` payloads.
- Seed (`ensure_seed`) runs once on empty DB; deleting buildings does not re-seed until the DB is reset.
- Editor scale: `SCALE = 20` px/m in `frontend/src/utils.ts`; snap 0.5 m.
- Frontend hardcodes some run parameters; there is no full params UI yet.
- No auth, multi-user, WebSockets, or test suite (pytest is listed but unused).
- Occupant IDs are `{group_id}:{i}`.

## Further reading

- [docs/how-it-works.md](docs/how-it-works.md) — human narrative of the system
- [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) — model limits and interpretation
- [README.md](README.md) — setup, workflow, known limitations
