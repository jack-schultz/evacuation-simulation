"""Discrete-time evacuation simulation engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.building import (
    BuildingLayout,
    FloodEmergency,
    FireEmergency,
    OccupantFrameState,
    OccupantStatus,
    SimulationFrame,
    SimulationParameters,
    SimulationResults,
)
from app.simulation.collision import build_collision_solids
from app.simulation.hazards import apply_hazards, hazard_radius_at
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
        }
        graph = self.graph_builder.build(layout, defaults)
        apply_hazards(graph, (layout.flood, layout.fire))

        boundary_solids = build_collision_solids(
            layout.spaces, layout.doors, layout.exits
        )
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        occupants = spawn_occupants(
            self.route_selector,
            layout,
            graph,
            params.occupant_radius_m,
            boundary_solids,
            spaces,
            doors,
            params.timestep_s,
        )
        queues: dict[str, ElementQueueState] = {}
        frames: list[SimulationFrame] = []
        t = 0.0
        next_frame_t = 0.0

        frames.append(self._capture_frame(t, occupants, layout.flood, layout.fire))
        next_frame_t = params.frame_interval_s

        while t < params.max_time_s:
            if all(o.status == OccupantStatus.EVACUATED for o in occupants):
                break

            t += params.timestep_s
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
                layout.flood,
                layout.fire,
                layout.obstacle_map,
                layout.width,
                layout.height,
            )

            if t + 1e-9 >= next_frame_t:
                frames.append(self._capture_frame(t, occupants, layout.flood, layout.fire))
                next_frame_t += params.frame_interval_s

        if not frames or frames[-1].t < t:
            frames.append(self._capture_frame(t, occupants, layout.flood, layout.fire))

        results = build_results(occupants, queues, t, graph=graph)
        return SimulationOutput(results=results, frames=frames)

    @staticmethod
    def _capture_frame(
        t: float,
        occupants: list[SimulatedOccupant],
        flood: FloodEmergency | None = None,
        fire: FireEmergency | None = None,
    ) -> SimulationFrame:
        return SimulationFrame(
            t=round(t, 3),
            flood_radius_m=hazard_radius_at(flood, t),
            fire_radius_m=hazard_radius_at(fire, t),
            occupants=[
                OccupantFrameState(
                    id=o.id,
                    x=round(o.x, 3),
                    y=round(o.y, 3),
                    status=o.status,
                    group_id=o.group_id,
                )
                for o in occupants
            ],
        )
