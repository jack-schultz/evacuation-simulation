"""Discrete-time evacuation simulation engine."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from app.domain.building import (
    BuildingLayout,
    OccupantFrameState,
    OccupantStatus,
    SimulationFrame,
    SimulationParameters,
    SimulationResults,
)
from app.simulation.collision import build_collision_solids
from app.simulation.flood import active_flood_plumes, apply_flood_plumes
from app.simulation.hazards import (
    active_fire_plumes,
    active_smoke_plumes,
    apply_hazards,
    apply_smoke_plumes,
    fire_emergencies_from_plumes,
    hazard_stair_spread_pending,
    max_hazard_radius_at,
    resolve_origin_smoke,
)
from app.simulation.flow import CapacityFlowModel, ElementQueueState, FlowModel
from app.simulation.graph import NavigationGraphBuilder
from app.simulation.movement import SimulatedOccupant, SpatialMovementModel
from app.simulation.results import build_results
from app.simulation.routing import DijkstraRouteSelector, RouteSelector
from app.simulation.spawn import spawn_occupants
from app.simulation.step import advance_timestep


@dataclass
class SimulationOutput:
    results: SimulationResults
    frames: list[SimulationFrame]


class SimulationEngine:
    """Runs a discrete-time evacuation over a building navigation graph.

    Occupants steer continuously toward fixed Dijkstra opening waypoints, collide via
    body radius and space boundaries, and pass doors/exits through width-limited
    apertures.
    """

    def __init__(
        self,
        route_selector: RouteSelector | None = None,
        flow_model: FlowModel | None = None,
        movement_model: SpatialMovementModel | None = None,
    ) -> None:
        self.route_selector = route_selector or DijkstraRouteSelector()
        self.flow_model = flow_model  # may be set per-run with radius
        self._flow_model_override = flow_model
        self.movement_model = movement_model or SpatialMovementModel()
        self.graph_builder = NavigationGraphBuilder()

    def run(self, layout: BuildingLayout, params: SimulationParameters) -> SimulationOutput:
        frames: list[SimulationFrame] = []
        stream = self.iter_run(layout, params)
        while True:
            try:
                frames.append(next(stream))
            except StopIteration as completed:
                output = completed.value
                output.frames = frames
                return output

    def iter_run(
        self, layout: BuildingLayout, params: SimulationParameters
    ) -> Generator[SimulationFrame, None, SimulationOutput]:
        if not layout.exits:
            raise ValueError("Building must have at least one exit")
        if not layout.occupant_groups:
            raise ValueError("Building must have at least one occupant group")

        if self._flow_model_override is not None:
            self.flow_model = self._flow_model_override
        else:
            self.flow_model = CapacityFlowModel(occupant_radius_m=params.occupant_radius_m)

        defaults = {
            "door_flow_per_s": params.door_flow_per_s,
            "stairs_flow_per_s": params.stairs_flow_per_s,
            "exit_flow_per_s": params.exit_flow_per_s,
            "corridor_density_per_m2": params.corridor_density_per_m2,
            "occupant_radius_m": params.occupant_radius_m,
            "stair_descent_speed_factor": params.stair_descent_speed_factor,
            "stair_ascent_speed_factor": params.stair_ascent_speed_factor,
        }
        graph = self.graph_builder.build(layout, defaults)
        origin_smoke = resolve_origin_smoke(layout)
        plumes0 = active_smoke_plumes(layout, 0.0)
        fire_plumes0 = active_fire_plumes(layout, 0.0)
        flood_plumes0 = active_flood_plumes(layout, 0.0)
        apply_hazards(
            graph,
            fire_emergencies_from_plumes(fire_plumes0),
        )
        apply_smoke_plumes(
            graph,
            plumes0,
            layout,
            visibility_m=(
                origin_smoke.visibility_m if origin_smoke is not None else 8.0
            ),
        )
        apply_flood_plumes(graph, flood_plumes0, layout)

        boundary_solids = build_collision_solids(
            layout.spaces, layout.doors, layout.exits
        )
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        floors = {f.id: f for f in layout.floors}
        occupants = spawn_occupants(
            self.route_selector,
            layout,
            graph,
            params.occupant_radius_m,
            boundary_solids,
            spaces,
            doors,
            params.timestep_s,
            defaults,
        )
        queues: dict[str, ElementQueueState] = {}
        t = 0.0
        next_frame_t = 0.0

        yield self._capture_frame(t, occupants, layout)
        next_frame_t = params.frame_interval_s
        last_frame_t = t

        while t < params.max_time_s:
            occupants_done = all(
                o.status in (OccupantStatus.EVACUATED, OccupantStatus.TRAPPED)
                for o in occupants
            )
            # Keep running after egress so fire/smoke can finish spreading through stairs.
            if occupants_done and not hazard_stair_spread_pending(
                layout, t, params.max_time_s
            ):
                break

            t += params.timestep_s
            plumes = active_smoke_plumes(layout, t)
            fire_plumes = active_fire_plumes(layout, t)
            flood_plumes = active_flood_plumes(layout, t)
            if not occupants_done:
                advance_timestep(
                    self.flow_model,
                    self.movement_model,
                    occupants,
                    graph,
                    queues,
                    params,
                    t,
                    boundary_solids,
                    spaces,
                    doors,
                    layout.floods[0] if layout.floods else None,
                    layout.fires[0] if layout.fires else None,
                    origin_smoke,
                    layout.obstacle_map,
                    layout.width,
                    layout.height,
                    floors,
                    plumes,
                    fire_plumes,
                    flood_plumes,
                    layout.obstacles,
                )

            if t + 1e-9 >= next_frame_t:
                yield self._capture_frame(t, occupants, layout)
                last_frame_t = t
                next_frame_t += params.frame_interval_s

        if last_frame_t < t:
            yield self._capture_frame(t, occupants, layout)

        results = build_results(occupants, queues, t, graph=graph)
        return SimulationOutput(results=results, frames=[])

    @staticmethod
    def _capture_frame(
        t: float,
        occupants: list[SimulatedOccupant],
        layout: BuildingLayout,
    ) -> SimulationFrame:
        return SimulationFrame(
            t=round(t, 3),
            flood_radius_m=max_hazard_radius_at(layout.floods, t),
            flood_rooms=active_flood_plumes(layout, t),
            fire_radius_m=max_hazard_radius_at(layout.fires, t),
            fire_floors=active_fire_plumes(layout, t),
            smoke_rooms=active_smoke_plumes(layout, t),
            occupants=[
                OccupantFrameState(
                    id=o.id,
                    x=round(o.x, 3),
                    y=round(o.y, 3),
                    status=o.status,
                    deceased=o.deceased,
                    group_id=o.group_id,
                    floor_id=o.floor_id,
                    climb_progress=(
                        round(o.climb_progress, 3)
                        if o.climb_progress is not None
                        else None
                    ),
                )
                for o in occupants
            ],
        )
