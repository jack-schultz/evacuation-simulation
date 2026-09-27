# Evacuation Simulation

Web application for building planners to model simplified evacuation paths and
estimate evacuation times. **Estimation only — not a safety certification or
regulatory compliance calculation.**

![img.png](img.png)

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

## Project structure

```text
evacuation-simulation/
├── backend/                 # FastAPI app + simulation engine
├── frontend/                # React + Vite + Konva editor
├── docs/
│   ├── how-it-works.md      # How the system works (humans)
│   └── ASSUMPTIONS.md       # Simulation assumptions
├── .env.example
└── README.md
```

## Documentation

* [docs/how-it-works.md](docs/how-it-works.md) — how the system works
* [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) — model assumptions

## Prerequisites

* Python **3.11–3.13** (3.13 recommended; avoid 3.14 until pydantic wheels catch up)
* Node.js 20+


## Typical workflow

1. Open the app — the example building loads automatically.
2. Edit rooms / doors / exits / occupants with the left tools.
3. Save the building.
4. Click **Run** to compute evacuation and animate occupants.
5. Use **Pause** / speed slider / **Reset**; inspect stats in the bottom bar.

## Important simulation assumptions

See [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md). Summary:

* Polygonal multi-floor geometry; shortest-path routing; illustrative fire/flood/smoke
* Capacity queues at doors/stairs/exits; stairs slow ascent/descent along a directed path
* Results are estimates only
