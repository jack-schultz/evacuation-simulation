# Simulation Assumptions

This document describes assumptions for the first-iteration evacuation model.
The application is an **estimation tool**, not a safety certification or
regulatory compliance calculation.

## Geometry

* Building geometry is simplified to axis-aligned rectangles (rooms, corridors,
  stairs).
* Coordinates use a top-left origin; one grid unit defaults to one metre
  (`meters_per_cell`).
* Space rectangle edges are solid for spatial movement; door and exit clear
  widths are the only gaps on those edges. Space edges do not alter the
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

The sidebar configures a circular flood with a centre, initial radius (metres),
spread speed (metres per second), and relative intensity (0-100). These settings
are saved with the building and snapshotted for each simulation.

The radius at simulation time `t` is `initial_radius + spread_speed_mps * t`.
The default spread speed is 0.1 m/s (6 m/min), compared with default unobstructed
walking speed of 1.2 m/s (72 m/min). This is an adjustable scenario assumption,
not an empirically calibrated rate. It is independent of walking speed: changing
occupant speed or crowding can change who escapes before an exit floods. Set
spread speed to zero to keep the original fixed-area scenario. Older layouts
without a spread speed use 0.1 m/s on new runs.

The flood and people use the same simulation clock. Each saved frame contains
its flood radius, so pausing, scrubbing, and playback speed changes keep them
synchronized. Old frames without a radius show their original fixed area.

At spawn, routes avoid crossing the initial flood and flooded exits, falling
back from an inaccessible preferred exit where possible. Routes remain fixed.
Every movement step checks the person's current position and remaining segment
against the expanded flood (at the end of that step). Newly flooded exits and
remaining paths into water trap occupants; water behind someone does not block
their remaining dry path. People already inside may move continuously outward,
with speed multiplied by `max(0.1, 1 - intensity / 100)` until they are dry.
Aperture steering targets are checked too. Zero intensity and disabled floods
preserve dry behavior. Finite timesteps introduce timing uncertainty up to a
step; smaller steps improve comparisons near flood arrival times.

Trapped occupants appear purple, count as remaining, and do not count as
evacuated. Partial evacuation has no total completion time. There is no mid-run
replanning or creation of new detours within rooms.

This remains a simplified radial scenario, not a water-depth or hydraulic
model. Walls do not contain water, and slopes, inflow, drainage, and water volume
are not modeled. A physical flood rate cannot be inferred from the available
layout alone. For context on terrain and hydraulic equation requirements, see
[USACE HEC-RAS 2D hydrodynamics](https://www.hec.usace.army.mil/confluence/rasdocs/ras1dtechref/6.2/theoretical-basis-for-one-dimensional-and-two-dimensional-hydrodynamic-calculations/2d-unsteady-flow-hydrodynamics).
