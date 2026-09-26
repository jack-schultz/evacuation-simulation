import type { BuildingLayout } from './types/building';

/** Choose the nearest space rectangle, retaining the current connection on ties. */
export function exitSpaceAt(
  layout: BuildingLayout,
  x: number,
  y: number,
  currentSpaceId?: string,
): string | undefined {
  let bestId: string | undefined;
  let bestDistance = Infinity;
  for (const space of layout.spaces) {
    const dx = Math.max(space.x - x, 0, x - space.x - space.width);
    const dy = Math.max(space.y - y, 0, y - space.y - space.height);
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
