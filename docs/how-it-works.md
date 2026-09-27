# How it works

A short mental model of the evacuation simulation app. For setup and run commands, see the [README](../README.md). For model limits, see [ASSUMPTIONS.md](ASSUMPTIONS.md).

**This tool estimates evacuation times from a simplified layout. It is not a safety certification or regulatory compliance calculation.**

## What this is

You sketch a floor plan in the browser (rooms, stairs, doors, exits, people), save it, and click **Run**. The server computes an evacuation timeline; the UI plays it back and shows summary stats (times, waits, congestion hotspots).

## Parts of the system

| Part | Role |
|------|------|
| **Editor** (React + Konva) | Draw and edit the layout; play animation frames |
| **API** (FastAPI) | Save buildings; create and run simulations |
| **Database** (SQLite) | Stores buildings and simulation snapshots, results, and frames as JSON |

```mermaid
flowchart LR
  Editor[LayoutEditor] -->|POST buildings| API[FastAPI]
  Editor -->|POST simulations then run| API
  API --> Engine[SimulationEngine]
  Engine --> DB[(SQLite)]
  API -->|frames plus results| Playback[ClientPlayback]
```

## Building blocks

- **Spaces** — Closed polygons (rooms or stairs). Draw by clicking
  corners and closing on the first point. Centroid nodes define connectivity
  between openings; people do not walk to room centroids as waypoints.
- **Doors** — Connect two spaces. Clear opening width limits how many people
  fit through at once (body radius vs width).
- **Exits** — Attached to a space; people leave the building here (also
  width-limited).
- **Occupant groups** — A count of people in a space, with walking speed and optional preferred exit.

Under the hood, the simulator builds a **navigation graph**: space interior points
(connectivity / spawn), doors, exits, and reflex-corner waypoints. Openings that
share a space are linked only when the segment stays inside the polygon; otherwise
routes detour via waypoints. Occupants steer along those nodes, collide with each
other and with space-edge segments, and squeeze through openings.

## What happens when you click Run

1. **Save** — If the layout is dirty, the app saves the building first.
2. **Create simulation** — The API copies (snapshots) the current layout and parameters into a new simulation record (`ready`).
3. **Run engine** (server, streamed as it runs):
   - Build the navigation graph.
   - Expand each occupant group into individuals.
   - Assign each person a route to a viable exit. Without a preferred exit, the initial assignment weighs walking time from the spawn point against projected queues at every door and exit on viable routes. Alternate doors from the starting room are considered even when they lead to the same exit. A reachable preferred exit remains binding. Routes stay fixed for the run.
   - Step through time (default 0.25 s). At each step, everyone tries to move
     toward their next waypoint at once; body collisions, space edges, and door/exit widths
     create jams — excess demand means waiting outside the opening.
  - Record animation frames on an interval, streaming each frame to the browser as soon as it is captured; aggregate statistics (evac times, waits, hotspots) when the run ends.
4. **Playback** — The browser starts animating as frames arrive. If it catches up with the calculation, it waits at the latest frame and resumes when more arrive. Final results appear when the run completes; the complete timeline and results are retained in SQLite.

## How to read results

- **Evacuation times** — Approximate travel time plus time spent waiting in
  crowds under the model’s rules (body collisions and opening width).
- **Wait / congestion hotspots** — Elements (doors, stairs, exits) where people queued.
- Treat numbers as planning estimates under simplified assumptions, not code-compliance evidence.

Full interpretation guidance: [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Known simplifications

- Multi-floor tabs with stacked plans, or same-floor linked stairs for a
  single-page multi-level plan; linked stairs use a directed slowed climb
  between stair centers (not continuous vertical physics).
- Illustrative circular fire (radial floor spread + stairs) and room-scoped
  smoke (through doors like flood, faster than fire; fire seeds smoke in rooms
  it reaches); flood fills each room separately,
  dumps down stairs before expanding past them, and rises only after a floor
  is filled; no panic or
  disability-specific movement.
- Space edges block movement except at door/exit widths; they do not carve the navigation graph.
- Occupants do not replan or follow crowds mid-run.

See [ASSUMPTIONS.md](ASSUMPTIONS.md) for the complete list.

### Rectangular obstacles

Choose **Obstacle** under Building tools, then click and drag to draw a rectangle.
Release to place it; Escape or right-click cancels. Obstacles snap to the 0.5 m
grid and belong to the active floor. Use Select to move them, or edit their
position, width and height in Properties. Delete, Undo, copy/paste and floor
duplication include obstacles.

Obstacle rectangles are saved with the layout and copied into simulation
snapshots. Routing adds clearance waypoints around their corners and connects
each occupant's actual spawn position to the visibility graph. Movement checks
the entire displacement against rectangles expanded by the occupant body
radius, including crowd separation pushes. Occupants cannot pass through
obstacles or gaps smaller than their body clearance. A completely blocked route
leaves the occupant trapped; spawn positions covered by an obstacle are moved
to nearby free space.
