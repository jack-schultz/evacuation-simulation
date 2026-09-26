import type { BuildingLayout } from './types/building';
import { pointInPolygon, polygonBBox } from './utils.ts';

/** Choose the nearest space polygon, retaining the current connection on ties. */
export function exitSpaceAt(
  layout: BuildingLayout,
  x: number,
  y: number,
  currentSpaceId?: string,
): string | undefined {
  let bestId: string | undefined;
  let bestDistance = Infinity;
  for (const space of layout.spaces) {
    if (pointInPolygon(x, y, space.vertices)) {
      const distance = 0;
      if (distance < bestDistance || (distance === bestDistance && space.id === currentSpaceId)) {
        bestId = space.id;
        bestDistance = distance;
      }
      continue;
    }
    const box = polygonBBox(space.vertices);
    const dx = Math.max(box.x - x, 0, x - box.x - box.width);
    const dy = Math.max(box.y - y, 0, y - box.y - box.height);
    const distance = dx * dx + dy * dy;
    if (distance < bestDistance || (distance === bestDistance && space.id === currentSpaceId)) {
      bestId = space.id;
      bestDistance = distance;
    }
  }
  return bestId;
}

export function moveExit(layout: BuildingLayout, exitId: string, x: number, y: number): BuildingLayout {
  return {
    ...layout,
    exits: layout.exits.map((exit) => exit.id === exitId ? {
      ...exit,
      x,
      y,
      connected_space_id: exitSpaceAt(layout, x, y, exit.connected_space_id) ?? exit.connected_space_id,
    } : exit),
  };
}
