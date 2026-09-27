export function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

export function snap(value: number, grid = 0.5): number {
  return Math.round(value / grid) * grid;
}

export const SCALE = 20; // pixels per metre

export type Point = [number, number];

/** Format a metres length for canvas dimension labels (0.5 m grid). */
export function formatLengthM(metres: number): string {
  const rounded = Math.round(metres * 10) / 10;
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  return `${text} m`;
}

export function distance(a: Point, b: Point): number {
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

export function polygonArea(vertices: Point[]): number {
  if (vertices.length < 3) return 0;
  let total = 0;
  const n = vertices.length;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = vertices[i];
    const [x2, y2] = vertices[(i + 1) % n];
    total += x1 * y2 - x2 * y1;
  }
  return Math.abs(total) / 2;
}

export function polygonCentroid(vertices: Point[]): Point {
  if (vertices.length === 0) return [0, 0];
  if (vertices.length === 1) return vertices[0];
  if (vertices.length === 2) {
    return [(vertices[0][0] + vertices[1][0]) / 2, (vertices[0][1] + vertices[1][1]) / 2];
  }
  let a = 0;
  let cx = 0;
  let cy = 0;
  const n = vertices.length;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = vertices[i];
    const [x2, y2] = vertices[(i + 1) % n];
    const cross = x1 * y2 - x2 * y1;
    a += cross;
    cx += (x1 + x2) * cross;
    cy += (y1 + y2) * cross;
  }
  a /= 2;
  if (Math.abs(a) < 1e-12) {
    const sx = vertices.reduce((s, p) => s + p[0], 0) / n;
    const sy = vertices.reduce((s, p) => s + p[1], 0) / n;
    return [sx, sy];
  }
  return [cx / (6 * a), cy / (6 * a)];
}

export function polygonBBox(vertices: Point[]): {
  x: number;
  y: number;
  width: number;
  height: number;
} {
  if (vertices.length === 0) return { x: 0, y: 0, width: 0, height: 0 };
  const xs = vertices.map((p) => p[0]);
  const ys = vertices.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

export function pointInPolygon(x: number, y: number, vertices: Point[]): boolean {
  if (vertices.length < 3) return false;
  let inside = false;
  const n = vertices.length;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const [xi, yi] = vertices[i];
    const [xj, yj] = vertices[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-30) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function orient(p: Point, q: Point, r: Point): number {
  return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
}

function pointOnSegment(p: Point, a: Point, b: Point, eps = 1e-9): boolean {
  const cross = orient(a, b, p);
  if (Math.abs(cross) > eps) return false;
  const dot = (p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1]);
  if (dot < -eps) return false;
  const len2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2;
  return dot <= len2 + eps;
}

/** Ray-casting inclusion that treats the boundary as outside. */
export function pointStrictlyInPolygon(
  x: number,
  y: number,
  vertices: Point[],
): boolean {
  if (vertices.length < 3) return false;
  const n = vertices.length;
  for (let i = 0; i < n; i++) {
    if (pointOnSegment([x, y], vertices[i], vertices[(i + 1) % n])) {
      return false;
    }
  }
  return pointInPolygon(x, y, vertices);
}

/** True if open segments properly cross (endpoint or colinear touch does not count). */
export function segmentsProperlyIntersect(
  a1: Point,
  a2: Point,
  b1: Point,
  b2: Point,
): boolean {
  const o1 = orient(a1, a2, b1);
  const o2 = orient(a1, a2, b2);
  const o3 = orient(b1, b2, a1);
  const o4 = orient(b1, b2, a2);
  if (
    Math.abs(o1) < 1e-12 &&
    Math.abs(o2) < 1e-12 &&
    Math.abs(o3) < 1e-12 &&
    Math.abs(o4) < 1e-12
  ) {
    return false;
  }
  return o1 * o2 < 0 && o3 * o4 < 0;
}

/**
 * True when two polygons share interior area.
 * Edge-adjacent or corner-touching polygons are allowed.
 */
export function polygonsOverlap(a: Point[], b: Point[]): boolean {
  if (a.length < 3 || b.length < 3) return false;
  const ba = polygonBBox(a);
  const bb = polygonBBox(b);
  if (
    ba.x + ba.width <= bb.x + 1e-9 ||
    bb.x + bb.width <= ba.x + 1e-9 ||
    ba.y + ba.height <= bb.y + 1e-9 ||
    bb.y + bb.height <= ba.y + 1e-9
  ) {
    return false;
  }

  const na = a.length;
  const nb = b.length;
  for (let i = 0; i < na; i++) {
    const a1 = a[i];
    const a2 = a[(i + 1) % na];
    for (let j = 0; j < nb; j++) {
      if (segmentsProperlyIntersect(a1, a2, b[j], b[(j + 1) % nb])) {
        return true;
      }
    }
  }

  for (const [x, y] of a) {
    if (pointStrictlyInPolygon(x, y, b)) return true;
  }
  for (const [x, y] of b) {
    if (pointStrictlyInPolygon(x, y, a)) return true;
  }

  const [cax, cay] = polygonCentroid(a);
  if (pointStrictlyInPolygon(cax, cay, b)) return true;
  const [cbx, cby] = polygonCentroid(b);
  return pointStrictlyInPolygon(cbx, cby, a);
}

export function samePoint(a: Point, b: Point, eps = 1e-9): boolean {
  return Math.abs(a[0] - b[0]) <= eps && Math.abs(a[1] - b[1]) <= eps;
}
