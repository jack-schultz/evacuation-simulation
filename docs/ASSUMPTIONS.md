# Simulation Assumptions

This document describes assumptions for the first-iteration evacuation model.
The application is an **estimation tool**, not a safety certification or
regulatory compliance calculation.

## Geometry

* Building spaces are closed polygons (rooms, stairs). Rectangles are
  the special case of four corners; the editor draws arbitrary polygons by
  clicking corners and closing on the start point.
* Layouts have named **floors** (storeys) with elevations. Spaces, doors,
  exits, and occupant groups carry a `floor_id`. Doors only connect spaces
  on the same floor. Stacked storeys share the same XY plan; collisions are
  floor-scoped.
* Coordinates use a top-left origin; one grid unit defaults to one metre
  (`meters_per_cell`).
* Each space has a centroid/interior node used for spawn start and to decide which
  openings share that room. People path **opening-to-opening** within a space
  along a **visibility graph** (doors, exits, and reflex-corner waypoints); raw
  Euclidean chords that leave the polygon are not used.
* Space polygon edges are solid for spatial movement; door and exit clear
  widths are the only gaps on those edges. Space edges do not alter the
  navigation graph beyond defining which openings may connect.
* Stairs spaces may set `linked_stair_id` to stairs on a **different floor**.
  Occupants walk a directed centreline along the stair polygon (ascent slower
  than descent), then continue on the partner floor. Capacity still limits
  concurrent climbers. A stair whose center lies inside a same-floor room is
  treated as an opening of that host. This is stacked 2D geometry with climb
  time — not a continuous 3D mesh.

## Occupant knowledge and behaviour

* Occupants initially know available routes to exits.
* Each occupant (expanded from a group) gets a fixed route at spawn. The route
  to each viable exit is found with Dijkstra; the initial exit assignment weighs
  walking time against projected queues at door and exit apertures across
  occupants. Multiple doors from the same room can share the crowd even when
  they lead to one exit.
* A reachable preferred exit remains binding. If a hazard blocks it, another
  viable exit is chosen where possible.
* Occupants do not dynamically replan, follow crowds, or exhibit panic.
* Walking speeds are configurable per group and constant during a run.

## Movement and congestion

* Discrete-time simulation (default timestep 0.25 s).
* Occupants steer continuously in 2D toward fixed route waypoints (doors and
  exits; plus the spawn space node only to leave the starting room; plus linked
  stair space nodes for teleport transfers) rather than sliding on a single
  shared edge line.
* Each person has a body radius (`occupant_radius_m`, default 0.25 m). Bodies
  cannot overlap; pairwise separation is resolved each timestep. Bodies also
  cannot cross space boundaries except through door/exit gaps.
* Each occupant tracks a **current space** and is clamped inside that space
  only. Membership flips when the body enters the next space through an
  admitted door aperture; pathing past that door requires the updated
  membership. This prevents discrete-step “teleports” through thin shared
  walls and stops route progress while a person is still stuck in the previous
  room.
* Door, stair, and exit openings admit about `floor(width / (2 * radius))`
  people at once (minimum 1). Wider openings allow more concurrent passage;
  excess demand piles up and waits outside the opening throat.
* Legacy `door_flow_per_s` / `exit_flow_per_s` / `stairs_flow_per_s` parameters
  remain on the API but no longer drive primary door throughput.
* Soft density limits may still apply via `FlowModel` for spaces that set
  `capacity_density_per_m2` (and for stairs via defaults).
* Capacity / aperture bookkeeping stays behind a `FlowModel` interface.

## Hazards not modelled

* Combustion, fuel, heat, toxicity, CFD smoke, and structural collapse are not
  simulated. Circular fire/flood/smoke are illustrative scenario overlays only.
* Disability-specific movement and panic are not simulated.
* Smoke reduces speed and usable sightline length, expands faster than fire, and
  spreads through linked stairs in both directions; it does not model optical
  density physics or incapacitation.

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


## Fire scenario

Fire is an optional circular hazard, configured independently of flood. Set the
centre, initial size (radius in metres), intensity (0-100%), and radial spread
rate (metres per second). Radius at time t is initial radius + spread rate * t;
zero spread keeps the area fixed. Disabled fire or zero intensity has no effect.
The orange overlay expands on the simulation clock and pauses with playback.
Settings are saved with the building and snapshotted for each run.

People avoid entering active fire and cannot use exits within it. People already
inside can escape outward along available routes at a speed multiplier of
max(0.1, 1 - intensity/100). Intensity is a relative scenario control, not a
physical temperature or heat-release rate. Routes are chosen at spawn; spreading
fire can trap people on their fixed route. Fire also spreads through linked
stairs (up and down), slower than smoke. With both fire and flood enabled, the
strongest restriction applies, including blocking by either hazard.

This illustrative model does not simulate combustion, fuel, heat,
ventilation, injury, or wall-dependent spread. It is an evacuation estimate,
not a fire engineering or safety certification model.

## Smoke scenario

Smoke is part of the **fire** disaster (`emit_smoke`, on by default). It expands
horizontally **faster** than the fire (about 2.5× the fire spread speed) and
starts from a larger initial radius. Inside the plume, walking speed is
multiplied by `max(0.25, 1 - intensity/100)`. Long visibility-graph chords are
heavily costed so people prefer shorter sightlines. Smoke does **not** hard-block
exits.

Both smoke and fire spread through linked stairs in **both** directions (up and
down). Stair links are treated as bidirectional for hazards even if only one
side sets `linked_stair_id`. After `smoke_stair_spread_delay_s` (smoke) or that
delay × 2.5 (fire), a weaker plume starts on the partner floor at the stair.
Fire uses the same path and rules, only slower. Playback continues after
everyone has evacuated until stair spread has finished (or max time). There is
no separate standalone smoke emergency in the editor.
