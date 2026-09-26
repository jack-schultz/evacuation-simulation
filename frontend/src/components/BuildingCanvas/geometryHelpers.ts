import type { BuildingLayout } from '../../types/building';
import { SCALE, pointInPolygon, polygonCentroid, type Point } from '../../utils';

export const SPACE_COLORS: Record<string, string> = {
  room: '#dbeafe',
  corridor: '#e2e8f0',
  stairs: '#fde68a',
};

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
