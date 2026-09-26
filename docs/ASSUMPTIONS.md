# Simulation Assumptions

This document describes assumptions for the first-iteration evacuation model.
The application is an **estimation tool**, not a safety certification or
regulatory compliance calculation.

## Geometry

* Building geometry is simplified to axis-aligned rectangles (rooms, corridors,
  stairs, walls).
* Coordinates use a top-left origin; one grid unit defaults to one metre
  (`meters_per_cell`).
* Walls are visual/blocked regions in the editor but do not currently carve
  holes in the navigation graph (spaces/doors/exits define connectivity).

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
* Movement is along a navigation graph (space centroids, doors, exits).
* Doors, stairs, and exits have maximum flow rates (occupants/second).
* Corridors may enforce approximate density limits.
* Excess demand produces queueing / wait time; capacity models are isolated
  behind a `FlowModel` interface for future replacement.

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
