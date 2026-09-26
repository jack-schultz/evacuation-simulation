export function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

export function snap(value: number, grid = 0.5): number {
  return Math.round(value / grid) * grid;
}

export const SCALE = 20; // pixels per metre
