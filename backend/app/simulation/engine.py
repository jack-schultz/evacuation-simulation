"""Discrete-time evacuation simulation engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.domain.building import (
    BuildingLayout,
    OccupantFrameState,
    OccupantStatus,
    SimulationFrame,
    SimulationParameters,
    SimulationResults,
)
from app.simulation.flow import CapacityFlowModel, ElementQueueState, FlowModel
from app.simulation.graph import EdgeKind, NavigationGraphBuilder
from app.simulation.movement import MovementModel, SimulatedOccupant
from app.simulation.results import build_results
from app.simulation.routing import DijkstraRouteSelector, RouteSelector, edge_between


@dataclass
class SimulationOutput:
    results: SimulationResults
    frames: list[SimulationFrame]


class SimulationEngine:
    """Runs a discrete-time evacuation over a building navigation graph.

    The engine expands occupant groups into individuals, assigns routes via a
    RouteSelector, and advances movement each timestep subject to a FlowModel.
    """

    def __init__(
        self,
        route_selector: RouteSelector | None = None,
        flow_model: FlowModel | None = None,
        movement_model: MovementModel | None = None,
    ) -> None:
        self.route_selector = route_selector or DijkstraRouteSelector()
        self.flow_model = flow_model or CapacityFlowModel()
        self.movement_model = movement_model or MovementModel()
        self.graph_builder = NavigationGraphBuilder()

    def run(self, layout: BuildingLayout, params: SimulationParameters) -> SimulationOutput:
        if not layout.exits:
            raise ValueError("Building must have at least one exit")
        if not layout.occupant_groups:
            raise ValueError("Building must have at least one occupant group")

        defaults = {
            "door_flow_per_s": params.door_flow_per_s,
            "stairs_flow_per_s": params.stairs_flow_per_s,
            "exit_flow_per_s": params.exit_flow_per_s,
            "corridor_density_per_m2": params.corridor_density_per_m2,
        }
        graph = self.graph_builder.build(layout, defaults)

        occupants = self._spawn_occupants(layout, graph)
        queues: dict[str, ElementQueueState] = {}
        frames: list[SimulationFrame] = []
        t = 0.0
        next_frame_t = 0.0

        frames.append(self._capture_frame(t, occupants))
        next_frame_t = params.frame_interval_s

        while t < params.max_time_s:
            if all(o.status == OccupantStatus.EVACUATED for o in occupants):
                break

            t += params.timestep_s
            self._step(occupants, graph, queues, params, t)

            if t + 1e-9 >= next_frame_t:
                frames.append(self._capture_frame(t, occupants))
                next_frame_t += params.frame_interval_s

        # Ensure final frame
        if not frames or frames[-1].t < t:
            frames.append(self._capture_frame(t, occupants))

        results = build_results(occupants, queues, t)
        return SimulationOutput(results=results, frames=frames)

    def _spawn_occupants(self, layout: BuildingLayout, graph) -> list[SimulatedOccupant]:
        occupants: list[SimulatedOccupant] = []
        spaces = {s.id: s for s in layout.spaces}

        for group in layout.occupant_groups:
            start_node = graph.space_node_ids[group.space_id]
            route = self.route_selector.select_route(
                graph, start_node, preferred_exit_id=group.destination_exit_id
            )
            space = spaces[group.space_id]
            for i in range(group.count):
                # Spread occupants within the room for visualization
                cols = max(int(space.width), 1)
                ox = space.x + 0.5 + (i % cols) * 0.4
                oy = space.y + 0.5 + (i // cols) * 0.4
                ox = min(ox, space.x + space.width - 0.3)
                oy = min(oy, space.y + space.height - 0.3)
                node = graph.nodes[start_node]
                occupants.append(
                    SimulatedOccupant(
                        id=f"{group.id}:{i}",
                        group_id=group.id,
                        speed_mps=group.walking_speed_mps,
                        route=list(route),
                        x=ox if group.count > 1 else node.x,
                        y=oy if group.count > 1 else node.y,
                    )
                )
        return occupants

    def _step(
        self,
        occupants: list[SimulatedOccupant],
        graph,
        queues: dict[str, ElementQueueState],
        params: SimulationParameters,
        t: float,
    ) -> None:
        # Group active occupants by the element they want to traverse next
        contenders: dict[str, list[SimulatedOccupant]] = defaultdict(list)
        element_edge = {}

        for occ in occupants:
            if occ.status == OccupantStatus.EVACUATED:
                continue
            nxt = occ.next_node_id
            if nxt is None:
                occ.status = OccupantStatus.EVACUATED
                occ.evacuated_at = t
                continue
            edge = edge_between(graph, occ.current_node_id, nxt)
            if edge is None:
                occ.status = OccupantStatus.TRAPPED
                continue
            contenders[edge.element_id].append(occ)
            element_edge[edge.element_id] = edge

        # Count occupants currently associated with corridor elements (density)
        occupants_on: dict[str, int] = defaultdict(int)
        for occ in occupants:
            if occ.status == OccupantStatus.EVACUATED:
                continue
            node = graph.nodes[occ.current_node_id]
            if node.kind.value == "space":
                occupants_on[node.ref_id] += 1

        allowed: dict[str, float] = {}  # occupant_id -> allowed distance this step

        for element_id, group in contenders.items():
            edge = element_edge[element_id]
            on_elem = occupants_on.get(element_id, 0)
            capacity = self.flow_model.calculate_capacity(edge, params.timestep_s, on_elem)

            q = queues.get(element_id)
            if q is None:
                kind = edge.kind.value
                if kind == "space":
                    kind = "corridor"
                q = ElementQueueState(element_id=element_id, element_type=kind)
                queues[element_id] = q

            q.max_throughput_this_step = capacity
            q.queue_length = len(group)
            q.peak_queue = max(q.peak_queue, len(group))

            # Priority: those already progressing on the edge, then FIFO by id
            ordered = sorted(
                group,
                key=lambda o: (0 if o.progress_on_edge > 0 else 1, o.id),
            )

            slots = capacity
            for occ in ordered:
                desired = self.movement_model.desired_move_distance(occ, params.timestep_s)
                if edge.kind in (EdgeKind.DOOR, EdgeKind.EXIT, EdgeKind.STAIRS):
                    # Flow-limited: consume one slot to fully proceed this step fractionally
                    if slots >= 1.0 or (slots > 0 and occ.progress_on_edge > 0):
                        allowed[occ.id] = desired
                        slots -= 1.0
                        q.throughput_this_step += 1.0
                    elif slots > 0:
                        # Partial progress proportional to remaining capacity
                        frac = slots
                        allowed[occ.id] = desired * frac
                        slots = 0.0
                        q.throughput_this_step += frac
                    else:
                        allowed[occ.id] = 0.0
                        q.total_wait_s += params.timestep_s
                else:
                    # Distance / density limited
                    if capacity == float("inf"):
                        allowed[occ.id] = desired
                    elif slots > 0:
                        allowed[occ.id] = desired
                        slots -= 0.5  # soft density consumption
                    else:
                        allowed[occ.id] = 0.0
                        q.total_wait_s += params.timestep_s

        for occ in occupants:
            if occ.status == OccupantStatus.EVACUATED:
                continue
            dist = allowed.get(occ.id, 0.0)
            waited = dist <= 0
            self.movement_model.apply_move(occ, graph, dist, params.timestep_s, waited)
            if occ.status == OccupantStatus.EVACUATED and occ.evacuated_at is None:
                occ.evacuated_at = t

    @staticmethod
    def _capture_frame(t: float, occupants: list[SimulatedOccupant]) -> SimulationFrame:
        return SimulationFrame(
            t=round(t, 3),
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
