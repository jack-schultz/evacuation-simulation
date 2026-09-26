import type { BuildingLayout } from './types/building';
import { pointInPolygon } from './utils.ts';

function distanceSquaredToSegment(x: number, y: number, ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;
  const t = lengthSquared === 0
    ? 0
    : Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / lengthSquared));
  const px = ax + t * dx;
  const py = ay + t * dy;
  return (x - px) ** 2 + (y - py) ** 2;
}

/** Choose the containing or nearest polygon, retaining the current connection on ties. */
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
    const distance = Math.min(...space.vertices.map(([ax, ay], i) => {
      const [bx, by] = space.vertices[(i + 1) % space.vertices.length];
      return distanceSquaredToSegment(x, y, ax, ay, bx, by);
    }));
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
