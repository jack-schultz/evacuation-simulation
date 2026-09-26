import type { BuildingLayout, Floor } from '../types/building';
import { DEFAULT_FLOOR_ID } from '../types/layout';

export const defaultFloors = (): Floor[] => [
  { id: DEFAULT_FLOOR_ID, name: 'Ground', elevation_m: 0, order: 0 },
];

export const emptyLayout = (): BuildingLayout => ({
  name: 'Untitled Building',
  width: 40,
  height: 40,
  meters_per_cell: 1,
  floors: defaultFloors(),
  spaces: [],
  doors: [],
  exits: [],
  occupant_groups: [],
});

export function ensureFloors(layout: BuildingLayout): Floor[] {
  if (layout.floors && layout.floors.length > 0) return layout.floors;
  return defaultFloors();
}

export function activeFloorId(layout: BuildingLayout, preferred?: string | null): string {
  const floors = ensureFloors(layout);
  if (preferred && floors.some((f) => f.id === preferred)) return preferred;
  return [...floors].sort((a, b) => a.order - b.order)[0]?.id ?? DEFAULT_FLOOR_ID;
}

export function entityFloorId(
  entity: { floor_id?: string | null },
  fallback = DEFAULT_FLOOR_ID,
): string {
  return entity.floor_id ?? fallback;
}

export function filterLayoutByFloor(layout: BuildingLayout, floorId: string): BuildingLayout {
  const spaces = layout.spaces.filter((s) => entityFloorId(s) === floorId);
  const spaceIds = new Set(spaces.map((s) => s.id));
  return {
    ...layout,
    spaces,
    doors: layout.doors.filter(
      (d) => entityFloorId(d) === floorId && d.connects.every((id) => spaceIds.has(id)),
    ),
    exits: layout.exits.filter(
      (e) => entityFloorId(e) === floorId && spaceIds.has(e.connected_space_id),
    ),
    occupant_groups: layout.occupant_groups.filter(
      (g) => entityFloorId(g) === floorId && spaceIds.has(g.space_id),
    ),
    flood:
      layout.flood && entityFloorId(layout.flood) === floorId ? layout.flood : null,
    fire: layout.fire && entityFloorId(layout.fire) === floorId ? layout.fire : null,
    smoke:
      layout.smoke && entityFloorId(layout.smoke) === floorId ? layout.smoke : null,
  };
}
