import type { BuildingLayout } from '../types/building';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const finiteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

function validateLayout(value: unknown): BuildingLayout {
  if (!isRecord(value)) throw new Error('The JSON file must contain a building layout object.');
  if (
    typeof value.name !== 'string'
    || !finiteNumber(value.width) || value.width <= 0
    || !finiteNumber(value.height) || value.height <= 0
    || !finiteNumber(value.meters_per_cell) || value.meters_per_cell <= 0
  ) {
    throw new Error('The layout needs a name, positive width and height, and meters_per_cell.');
  }
  for (const key of ['spaces', 'doors', 'exits', 'occupant_groups'] as const) {
    if (!Array.isArray(value[key])) throw new Error(`The layout is missing its ${key} list.`);
  }
  const spaces = value.spaces as unknown[];
  const doors = value.doors as unknown[];
  const exits = value.exits as unknown[];
  const groups = value.occupant_groups as unknown[];
  for (const [index, space] of spaces.entries()) {
    if (
      !isRecord(space) || typeof space.id !== 'string' || typeof space.name !== 'string'
      || !['room', 'corridor', 'stairs'].includes(String(space.type))
      || !Array.isArray(space.vertices) || space.vertices.length < 3
      || !space.vertices.every((point) => Array.isArray(point) && point.length === 2
        && finiteNumber(point[0]) && finiteNumber(point[1]))
    ) throw new Error(`Space ${index + 1} is invalid.`);
  }
  for (const [index, door] of doors.entries()) {
    if (!isRecord(door) || typeof door.id !== 'string' || typeof door.name !== 'string'
      || !finiteNumber(door.x) || !finiteNumber(door.y) || !finiteNumber(door.width)
      || !Array.isArray(door.connects) || door.connects.length !== 2
      || !door.connects.every((id) => typeof id === 'string')) {
      throw new Error(`Door ${index + 1} is invalid.`);
    }
  }
  for (const [index, exit] of exits.entries()) {
    if (!isRecord(exit) || typeof exit.id !== 'string' || typeof exit.name !== 'string'
      || !finiteNumber(exit.x) || !finiteNumber(exit.y) || !finiteNumber(exit.width)
      || typeof exit.connected_space_id !== 'string') {
      throw new Error(`Exit ${index + 1} is invalid.`);
    }
  }
  for (const [index, group] of groups.entries()) {
    if (!isRecord(group) || typeof group.id !== 'string' || typeof group.name !== 'string'
      || !finiteNumber(group.count) || typeof group.space_id !== 'string'
      || !finiteNumber(group.walking_speed_mps)) {
      throw new Error(`Occupant group ${index + 1} is invalid.`);
    }
  }
  return value as unknown as BuildingLayout;
}

export async function readLayoutFile(file: File): Promise<BuildingLayout> {
  if (!file.name.toLowerCase().endsWith('.json')) throw new Error('Choose a .json map file.');
  let data: unknown;
  try {
    data = JSON.parse(await file.text());
  } catch {
    throw new Error('This file does not contain valid JSON.');
  }
  if (isRecord(data) && data.format === 'evacuation-simulation-layout') {
    return validateLayout(data.layout);
  }
  return validateLayout(data);
}

export function downloadLayoutFile(layout: BuildingLayout): void {
  const blob = new Blob([
    JSON.stringify({ format: 'evacuation-simulation-layout', version: 1, layout }, null, 2),
  ], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const safeName = layout.name.trim().replace(/[^\w-]+/g, '-').replace(/^-|-$/g, '') || 'building-map';
  link.href = url;
  link.download = `${safeName}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
