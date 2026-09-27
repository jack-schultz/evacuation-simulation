import type { BuildingLayout, Space } from '../../types/building.ts';
import {
  SCALE,
  pointInPolygon,
  polygonCentroid,
  polygonsOverlap,
  type Point,
} from '../../utils.ts';

export const SPACE_COLORS: Record<string, string> = {
  room: '#dbeafe',
  corridor: '#e2e8f0',
  stairs: '#fde68a',
};

export const OVERLAP_FILL = '#fecaca';

/**
 * Non-stair spaces on the same floor that share interior area.
 * Stairs may nest inside a host room; edge-adjacent rooms are fine.
 */
export function findOverlappingSpaceIds(layout: BuildingLayout): Set<string> {
  const overlapping = new Set<string>();
  const byFloor = new Map<string, Space[]>();
  for (const space of layout.spaces) {
    if (space.type === 'stairs') continue;
    const floorId = space.floor_id ?? 'floor-0';
    const group = byFloor.get(floorId);
    if (group) group.push(space);
    else byFloor.set(floorId, [space]);
  }
  for (const spaces of byFloor.values()) {
    for (let i = 0; i < spaces.length; i++) {
      for (let j = i + 1; j < spaces.length; j++) {
        if (polygonsOverlap(spaces[i].vertices, spaces[j].vertices)) {
          overlapping.add(spaces[i].id);
          overlapping.add(spaces[j].id);
        }
      }
    }
  }
  return overlapping;
}

export function spaceCentroid(vertices: Point[]): Point {
  return polygonCentroid(vertices);
}

export function findNearestSpaces(
  layout: BuildingLayout,
  x: number,
  y: number,
  count: number,
): string[] {
  return [...layout.spaces]
    .map((s) => {
      const [cx, cy] = spaceCentroid(s.vertices);
      const d = (cx - x) ** 2 + (cy - y) ** 2;
      return { id: s.id, d };
    })
    .sort((a, b) => a.d - b.d)
    .slice(0, count)
    .map((s) => s.id);
}

export function spaceContaining(layout: BuildingLayout, x: number, y: number): string | null {
  const hit = layout.spaces.find((s) => pointInPolygon(x, y, s.vertices));
  return hit?.id ?? null;
}

export function toFlatPoints(vertices: Point[]): number[] {
  return vertices.flatMap(([x, y]) => [x * SCALE, y * SCALE]);
}
