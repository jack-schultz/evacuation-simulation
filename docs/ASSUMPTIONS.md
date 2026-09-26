# Simulation Assumptions

This document describes assumptions for the first-iteration evacuation model.
The application is an **estimation tool**, not a safety certification or
regulatory compliance calculation.

## Geometry

* Building geometry is simplified to axis-aligned rectangles (rooms, corridors,
  stairs, walls).
* Coordinates use a top-left origin; one grid unit defaults to one metre
  (`meters_per_cell`).
* Space rectangle edges are solid for spatial movement; door and exit clear
  widths are the only gaps on those edges. Optional explicit walls are additional
  obstacles (also punched at openings). Neither space edges nor walls alter the
  navigation graph (spaces/doors/exits define connectivity).

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
* Occupants steer continuously in 2D toward fixed route waypoints (space
  centroids, doors, exits) rather than sliding on a single shared edge line.
* Each person has a body radius (`occupant_radius_m`, default 0.25 m). Bodies
  cannot overlap; pairwise separation is resolved each timestep. Bodies also
  cannot cross space boundaries or solid walls except through door/exit gaps.
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
