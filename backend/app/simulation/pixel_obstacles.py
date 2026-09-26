"""Collision checks against the imported binary floor-plan raster."""

from __future__ import annotations

from app.domain.building import PixelObstacleMap


def position_is_walkable(
    obstacle_map: PixelObstacleMap | None,
    x: float,
    y: float,
    radius: float,
    world_width: float,
    world_height: float,
) -> bool:
    if obstacle_map is None:
        return True
    cell_w = world_width / obstacle_map.width
    cell_h = world_height / obstacle_map.height
    min_x = max(0, int((x - radius) / cell_w))
    max_x = min(obstacle_map.width - 1, int((x + radius) / cell_w))
    min_y = max(0, int((y - radius) / cell_h))
    max_y = min(obstacle_map.height - 1, int((y + radius) / cell_h))
    radius_sq = radius * radius
    for py in range(min_y, max_y + 1):
        row = obstacle_map.rows[py]
        for px in range(min_x, max_x + 1):
            if row[px] != "1":
                continue
            left, top = px * cell_w, py * cell_h
            nearest_x = min(max(x, left), left + cell_w)
            nearest_y = min(max(y, top), top + cell_h)
            if (x - nearest_x) ** 2 + (y - nearest_y) ** 2 < radius_sq:
                return False
    return True
