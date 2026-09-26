export function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

export function snap(value: number, grid = 0.5): number {
  return Math.round(value / grid) * grid;
}

export const SCALE = 20; // pixels per metre

export type Point = [number, number];

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

export function samePoint(a: Point, b: Point, eps = 1e-9): boolean {
  return Math.abs(a[0] - b[0]) <= eps && Math.abs(a[1] - b[1]) <= eps;
}
