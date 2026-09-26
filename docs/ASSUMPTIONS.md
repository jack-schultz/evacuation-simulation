# Simulation Assumptions

This document describes assumptions for the first-iteration evacuation model.
The application is an **estimation tool**, not a safety certification or
regulatory compliance calculation.

## Geometry

* Building spaces are closed polygons (rooms, corridors, stairs). Rectangles are
  the special case of four corners; the editor draws arbitrary polygons by
  clicking corners and closing on the start point.
* Coordinates use a top-left origin; one grid unit defaults to one metre
  (`meters_per_cell`).
* Each space has a centroid node used for spawn start and to decide which
  openings share that room. People path **opening-to-opening** within a space
  (door↔door, door↔exit); they do not walk to room centroids as waypoints.
* Space polygon edges are solid for spatial movement; door and exit clear
  widths are the only gaps on those edges. Space edges do not alter the
  navigation graph beyond defining which openings may connect.

## Occupant knowledge and behaviour

* Occupants initially know available routes to exits.
* Each occupant (expanded from a group) selects a single shortest-path route
  at the start of the simulation (Dijkstra by distance).
* Optional preferred-exit assignment is supported; otherwise the nearest exit
  by path length is used.
* Occupants do not dynamically replan, follow crowds, or exhibit panic.
* Walking speeds are configurable per group and constant during a run.

## Movement and congestion

* Discrete-time simulation (default timestep 0.25 s).
* Occupants steer continuously in 2D toward fixed route waypoints (doors and
  exits; plus the spawn space node only to leave the starting room) rather than
  sliding on a single shared edge line.
* Each person has a body radius (`occupant_radius_m`, default 0.25 m). Bodies
  cannot overlap; pairwise separation is resolved each timestep. Bodies also
  cannot cross space boundaries except through door/exit gaps.
* Each occupant tracks a **current space** and is clamped inside that space
  until they transit an admitted door aperture into the next space on their
  route (then membership updates). This prevents discrete-step “teleports”
  through thin shared walls.
* Door, stair, and exit openings admit about `floor(width / (2 * radius))`
  people at once (minimum 1). Wider openings allow more concurrent passage;
  excess demand piles up and waits outside the opening throat.
* Legacy `door_flow_per_s` / `exit_flow_per_s` / `stairs_flow_per_s` parameters
  remain on the API but no longer drive primary door throughput.
* Corridors may still enforce soft density limits via `FlowModel`.
* Capacity / aperture bookkeeping stays behind a `FlowModel` interface.

## Hazards not modelled

* Fire / smoke dynamics are not simulated.
* Structural collapse is not simulated.
* Toxicity, heat, visibility loss, and disability-specific movement are not
  simulated.
* Human panic is not explicitly simulated.

## Results interpretation

* Reported times are approximate travel + wait estimates under the above rules.
* Congestion hotspots highlight elements where queueing occurred.
* Do not use results as the sole basis for life-safety design decisions without
  qualified engineering review and validated methods.


## Flood emergency scenarios

The sidebar can add, disable, remove, and edit one circular flood area (centre X/Y,
 radius in metres, and relative intensity from 0 to 100). It is saved with the
building and snapshotted with each simulation. Reset playback before editing it.

Flood geometry and intensity remain constant throughout a run. At any positive
intensity, routes cannot enter or cross the flood, and exits inside or on the
flood boundary cannot be used (including preferred exits). Occupants already
inside may traverse directed graph segments that move continuously farther from
the flood centre. These escape segments receive a speed factor of
`max(0.1, 1 - intensity / 100)`, applied to the whole segment. Reverse movement
back into the flood is blocked. Dry routes still minimize distance; escape routes
account for their reduced speed. Zero intensity and disabled floods preserve
baseline behavior.

If a preferred exit has no permitted route, occupants try another exit. Occupants
without any permitted route remain trapped (purple), count as remaining, and do
not count as evacuated. A partial evacuation has no total completion time.
The graph cannot create new detours within a room: if existing door/space/exit
segments offer no outward or dry path, occupants are reported as trapped.

This is a deliberately simplified scenario model, not water depth, flow velocity,
hydrodynamic spread, or a calibrated flood safety threshold. Walls do not contain
water in this model. Occupants know the flood at spawn and keep their chosen route;
there is no changing flood or mid-run replanning. Movement stops at graph nodes
in affected scenarios to apply each segment's speed factor independently.
