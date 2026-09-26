# Evacuation Simulation

Web application for building planners to model simplified evacuation paths and
estimate evacuation times. **Estimation only — not a safety certification or
regulatory compliance calculation.**

## What was implemented (iteration 1)

* FastAPI backend with domain/service separation and SQLite persistence
* Building CRUD API + seeded example (two offices, corridor bottleneck, ~85 occupants)
* Navigation graph + Dijkstra routing + capacity-based congestion model
* Discrete-time simulation engine returning animation frames and statistics
* React + TypeScript + Vite frontend with Konva layout editor
* Run / pause / play / reset / speed controls and results panel

## Project structure

```text
evacuation-simulation/
├── backend/                 # FastAPI app + simulation engine
├── frontend/                # React + Vite + Konva editor
├── docs/
│   ├── how-it-works.md      # How the system works (humans)
│   └── ASSUMPTIONS.md       # Simulation assumptions
├── AGENTS.md                # Context for coding agents
├── .env.example
└── README.md
```

## Documentation

* [docs/how-it-works.md](docs/how-it-works.md) — how the system works
* [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) — model assumptions
* [AGENTS.md](AGENTS.md) — context for coding agents

## Prerequisites

* Python **3.11–3.13** (3.13 recommended; avoid 3.14 until pydantic wheels catch up)
* Node.js 20+

## Setup

```bash
# From repo root
cp .env.example .env

# Backend
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

## Run

Terminal 1 — backend:

```bash
source .venv/bin/activate
cd backend
mkdir -p data
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — frontend:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173

API docs: http://localhost:8000/docs  
Health: http://localhost:8000/api/health

## Typical workflow

1. Open the app — the example building loads automatically.
2. Edit rooms / doors / exits / occupants with the left tools.
3. Save the building.
4. Click **Run** to compute evacuation and animate occupants.
5. Use **Pause** / speed slider / **Reset**; inspect stats in the bottom bar.

## Important simulation assumptions

See [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md). Summary:

* Rectangle geometry; shortest-path routing; no fire/smoke/panic
* Capacity queues at doors/corridors/stairs/exits
* Results are estimates only

## Known limitations

* Single-floor style canvas (linked stairs teleport between paired stair centers; not continuous multi-level physics)
* Space edges block movement except at door/exit gaps; connectivity is doors, exits, and linked stairs
* No live WebSocket streaming (full timeline computed server-side)
* No authentication or multi-user collaboration
* Congestion model is intentionally simple

## Recommended next steps

* Smarter route choice (familiar exits, congestion avoidance, replanning)
* Continuous-space / social-force movement models
* True multi-floor geometry and stair bidirectional flow (beyond linked-stair teleport)
* Hazard layers (smoke) affecting speed and visibility
* Import from DXF / simple BIM subsets
* Scenario comparison and report export

## License

Use and modify for planning and research. Do not present outputs as code
compliance without appropriate professional validation.
