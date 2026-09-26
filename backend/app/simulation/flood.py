"""Compatibility helpers for the flood scenario."""
from app.simulation.hazards import (
    HazardRouteSelector as FloodRouteSelector,
    hazard_radius_at as flood_radius_at,
    segment_speed_factor,
    apply_hazards,
)


def apply_flood(graph, flood, t=0.0):
    apply_hazards(graph, (flood,), t)
