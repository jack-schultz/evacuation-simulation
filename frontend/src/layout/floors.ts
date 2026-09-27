import type { BuildingLayout, Floor } from '../types/building';
import { uid } from '../utils.ts';
import { entityFloorId, ensureFloors } from './emptyLayout.ts';

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function nextFloorId(existing: Floor[]): string {
  const used = new Set(existing.map((f) => f.id));
  let n = existing.reduce((m, f) => Math.max(m, f.order), -1) + 1;
  let id = `floor-${n}`;
  while (used.has(id)) {
    n += 1;
    id = `floor-${n}`;
  }
  return id;
}

/** Duplicate a floor and all geometry/occupants on it (stair links across floors are cleared). */
export function duplicateFloor(
  layout: BuildingLayout,
  floorId: string,
): { layout: BuildingLayout; newFloorId: string } | null {
  const floors = ensureFloors(layout);
  const source = floors.find((f) => f.id === floorId);
  if (!source) return null;

  const newFloorId = nextFloorId(floors);
  const order = floors.reduce((m, f) => Math.max(m, f.order), -1) + 1;
  const elev =
    floors.reduce((m, f) => Math.max(m, f.elevation_m), source.elevation_m - 3.2) + 3.2;
  const newFloor: Floor = {
    id: newFloorId,
    name: `${source.name} copy`,
    elevation_m: elev,
    order,
  };

  const spacesOnFloor = layout.spaces.filter((s) => entityFloorId(s) === floorId);
  const spaceIds = new Set(spacesOnFloor.map((s) => s.id));
  const doorsOnFloor = layout.doors.filter(
    (d) => entityFloorId(d) === floorId && d.connects.every((id) => spaceIds.has(id)),
  );
  const exitsOnFloor = layout.exits.filter(
    (e) => entityFloorId(e) === floorId && spaceIds.has(e.connected_space_id),
  );
  const groupsOnFloor = layout.occupant_groups.filter(
    (g) => entityFloorId(g) === floorId && spaceIds.has(g.space_id),
  );

  const idMap = new Map<string, string>();
  for (const space of spacesOnFloor) {
    idMap.set(space.id, uid(space.type === 'stairs' ? 'stairs' : 'room'));
  }
  for (const door of doorsOnFloor) {
    idMap.set(door.id, uid('door'));
  }
  for (const exit of exitsOnFloor) {
    idMap.set(exit.id, uid('exit'));
  }
  for (const group of groupsOnFloor) {
    idMap.set(group.id, uid('group'));
  }

  const spaces = spacesOnFloor.map((space) => {
    const linked = space.linked_stair_id;
    return {
      ...cloneJson(space),
      id: idMap.get(space.id)!,
      name: `${space.name} copy`,
      floor_id: newFloorId,
      // Keep same-floor links; drop cross-floor stair portals.
      linked_stair_id:
        linked && idMap.has(linked) ? idMap.get(linked)! : null,
    };
  });

  const doors = doorsOnFloor.map((door) => ({
    ...cloneJson(door),
    id: idMap.get(door.id)!,
    floor_id: newFloorId,
    connects: [
      idMap.get(door.connects[0]) ?? door.connects[0],
      idMap.get(door.connects[1]) ?? door.connects[1],
    ] as [string, string],
  }));

  const exits = exitsOnFloor.map((exit) => ({
    ...cloneJson(exit),
    id: idMap.get(exit.id)!,
    floor_id: newFloorId,
    connected_space_id: idMap.get(exit.connected_space_id) ?? exit.connected_space_id,
  }));

  const occupant_groups = groupsOnFloor.map((group) => {
    let destination = group.destination_exit_id ?? null;
    if (destination && idMap.has(destination)) {
      destination = idMap.get(destination)!;
    }
    return {
      ...cloneJson(group),
      id: idMap.get(group.id)!,
      floor_id: newFloorId,
      space_id: idMap.get(group.space_id) ?? group.space_id,
      destination_exit_id: destination,
    };
  });

  return {
    newFloorId,
    layout: {
      ...layout,
      floors: [...floors, newFloor],
      obstacles: [...(layout.obstacles ?? []), ...(layout.obstacles ?? [])
        .filter(o => entityFloorId(o) === floorId)
        .map(o => ({ ...o, id: uid('obstacle'), floor_id: newFloorId }))],
      spaces: [...layout.spaces, ...spaces],
      doors: [...layout.doors, ...doors],
      exits: [...layout.exits, ...exits],
      occupant_groups: [...layout.occupant_groups, ...occupant_groups],
    },
  };
}

/** Remove a floor and everything on it. Returns null if it is the last floor. */
export function deleteFloor(
  layout: BuildingLayout,
  floorId: string,
): BuildingLayout | null {
  const floors = ensureFloors(layout);
  if (floors.length <= 1) return null;
  if (!floors.some((f) => f.id === floorId)) return null;

  const removedSpaceIds = new Set(
    layout.spaces.filter((s) => entityFloorId(s) === floorId).map((s) => s.id),
  );

  const nextFloors = floors.filter((f) => f.id !== floorId);
  const clearHazard = <T extends { floor_id?: string | null }>(
    hazard: T | null | undefined,
  ): T | null => {
    if (!hazard) return null;
    return entityFloorId(hazard) === floorId ? null : hazard;
  };

  return {
    ...layout,
    floors: nextFloors,
    obstacles: (layout.obstacles ?? []).filter(o => entityFloorId(o) !== floorId),
    spaces: layout.spaces
      .filter((s) => entityFloorId(s) !== floorId)
      .map((s) =>
        s.linked_stair_id && removedSpaceIds.has(s.linked_stair_id)
          ? { ...s, linked_stair_id: null }
          : s,
      ),
    doors: layout.doors.filter((d) => entityFloorId(d) !== floorId),
    exits: layout.exits.filter((e) => entityFloorId(e) !== floorId),
    occupant_groups: layout.occupant_groups.filter(
      (g) => entityFloorId(g) !== floorId,
    ),
    floods: (layout.floods ?? []).filter((f) => entityFloorId(f) !== floorId),
    fires: (layout.fires ?? []).filter((f) => entityFloorId(f) !== floorId),
    smoke: clearHazard(layout.smoke),
  };
}
