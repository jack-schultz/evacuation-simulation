"""Aggregate simulation results from occupant states."""

from __future__ import annotations

from app.domain.building import (
    CongestionHotspot,
    OccupantResult,
    OccupantStatus,
    SimulationResults,
)
from app.simulation.flow import ElementQueueState
from app.simulation.movement import SimulatedOccupant


def build_results(
    occupants: list[SimulatedOccupant],
    queues: dict[str, ElementQueueState],
    simulation_time_s: float,
) -> SimulationResults:
    evacuated = [o for o in occupants if o.status == OccupantStatus.EVACUATED]
    remaining = [o for o in occupants if o.status != OccupantStatus.EVACUATED]

    evac_times = [o.evacuated_at for o in evacuated if o.evacuated_at is not None]
    total_evac = max(evac_times) if evac_times else (simulation_time_s if not remaining else None)

    hotspots = [
        CongestionHotspot(
            element_id=q.element_id,
            element_type=q.element_type,  # type: ignore[arg-type]
            total_wait_s=round(q.total_wait_s, 3),
            peak_queue=q.peak_queue,
        )
        for q in queues.values()
        if q.total_wait_s > 0 or q.peak_queue > 1
    ]
    hotspots.sort(key=lambda h: h.total_wait_s, reverse=True)

    occupant_results = [
        OccupantResult(
            id=o.id,
            group_id=o.group_id,
            evacuated=o.status == OccupantStatus.EVACUATED,
            distance_m=round(o.distance_m, 3),
            travel_time_s=round(o.travel_time_s, 3),
            wait_time_s=round(o.wait_time_s, 3),
            total_time_s=round((o.evacuated_at if o.evacuated_at is not None else simulation_time_s), 3),
            route_node_ids=list(o.route),
        )
        for o in occupants
    ]

    avg_evac = sum(evac_times) / len(evac_times) if evac_times else None
    max_evac = max(evac_times) if evac_times else None
    avg_dist = (
        sum(o.distance_m for o in evacuated) / len(evacuated) if evacuated else None
    )
    avg_wait = (
        sum(o.wait_time_s for o in occupants) / len(occupants) if occupants else None
    )

    return SimulationResults(
        total_occupants=len(occupants),
        evacuated_count=len(evacuated),
        remaining_count=len(remaining),
        total_evacuation_time_s=round(total_evac, 3) if total_evac is not None else None,
        average_evacuation_time_s=round(avg_evac, 3) if avg_evac is not None else None,
        max_evacuation_time_s=round(max_evac, 3) if max_evac is not None else None,
        average_distance_m=round(avg_dist, 3) if avg_dist is not None else None,
        average_wait_time_s=round(avg_wait, 3) if avg_wait is not None else None,
        congestion_hotspots=hotspots,
        occupants=occupant_results,
    )
