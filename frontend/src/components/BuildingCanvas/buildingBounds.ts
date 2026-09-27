import type { BuildingLayout } from '../../types/building';
import { polygonBBox, snap } from '../../utils.ts';

export const BUILDING_MIN_M = 1;
export const BUILDING_MAX_M = 200;

export type BuildingResizeHandle = 'e' | 's' | 'ne' | 'se' | 'sw';

/** Minimum width/height so existing layout content stays inside the footprint. */
export function contentMinSize(layout: BuildingLayout): { width: number; height: number } {
  let maxX = 0;
  let maxY = 0;

  for (const space of layout.spaces) {
    const box = polygonBBox(space.vertices);
    maxX = Math.max(maxX, box.x + box.width);
    maxY = Math.max(maxY, box.y + box.height);
  }
  for (const obstacle of layout.obstacles ?? []) {
    maxX = Math.max(maxX, obstacle.x + obstacle.width);
    maxY = Math.max(maxY, obstacle.y + obstacle.height);
  }
  for (const door of layout.doors) {
    maxX = Math.max(maxX, door.x);
    maxY = Math.max(maxY, door.y);
  }
  for (const exit of layout.exits) {
    maxX = Math.max(maxX, exit.x);
    maxY = Math.max(maxY, exit.y);
  }
  for (const group of layout.occupant_groups) {
    if (group.spawn_x != null) maxX = Math.max(maxX, group.spawn_x);
    if (group.spawn_y != null) maxY = Math.max(maxY, group.spawn_y);
  }
  for (const hazard of [...(layout.floods ?? []), ...(layout.fires ?? [])]) {
    maxX = Math.max(maxX, hazard.x);
    maxY = Math.max(maxY, hazard.y);
  }

  return {
    width: Math.max(BUILDING_MIN_M, maxX),
    height: Math.max(BUILDING_MIN_M, maxY),
  };
}

export function clampBuildingSize(
  width: number,
  height: number,
  layout: BuildingLayout,
): { width: number; height: number } {
  const min = contentMinSize(layout);
  return {
    width: Math.min(BUILDING_MAX_M, Math.max(min.width, snap(width))),
    height: Math.min(BUILDING_MAX_M, Math.max(min.height, snap(height))),
  };
}

export function sizeFromHandleDrag(
  handle: BuildingResizeHandle,
  pointerX: number,
  pointerY: number,
  currentWidth: number,
  currentHeight: number,
): { width: number; height: number } {
  let width = currentWidth;
  let height = currentHeight;
  if (handle === 'e' || handle === 'ne' || handle === 'se') {
    width = pointerX;
  }
  if (handle === 's' || handle === 'se' || handle === 'sw') {
    height = pointerY;
  }
  return { width, height };
}
