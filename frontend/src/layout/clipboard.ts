import type {
  BuildingLayout,
  Door,
  Exit,
  OccupantGroup,
  Obstacle,
  Selection,
  Space,
} from '../types/building';
import { pointInPolygon, snap, uid, type Point } from '../utils.ts';

export interface ClipboardPayload {
  obstacles?: Obstacle[];
  spaces: Space[];
  doors: Door[];
  exits: Exit[];
  occupant_groups: OccupantGroup[];
}

export const PASTE_OFFSET_M = 1;

let clipboard: ClipboardPayload | null = null;

export function hasClipboard(): boolean {
  if (!clipboard) return false;
  return (
    (clipboard.obstacles?.length ?? 0) > 0
    || clipboard.spaces.length > 0
    || clipboard.doors.length > 0
    || clipboard.exits.length > 0
    || clipboard.occupant_groups.length > 0
  );
}

export function getClipboard(): ClipboardPayload | null {
  return clipboard;
}

export function setClipboard(payload: ClipboardPayload | null): void {
  clipboard = payload;
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function extractSelection(
  layout: BuildingLayout,
  selection: Selection,
): ClipboardPayload {
  const spaceIds = new Set(
    selection.filter((r) => r.kind === 'space').map((r) => r.id),
  );
  const doorIds = new Set(
    selection.filter((r) => r.kind === 'door').map((r) => r.id),
  );
  const exitIds = new Set(
    selection.filter((r) => r.kind === 'exit').map((r) => r.id),
  );
  const groupIds = new Set(
    selection.filter((r) => r.kind === 'occupants').map((r) => r.id),
  );

  return {
    obstacles: (layout.obstacles ?? []).filter(o =>
      selection.some(r => r.kind === 'obstacle' && r.id === o.id)).map(cloneJson),
    spaces: layout.spaces.filter((s) => spaceIds.has(s.id)).map(cloneJson),
    doors: layout.doors.filter((d) => doorIds.has(d.id)).map(cloneJson),
    exits: layout.exits.filter((e) => exitIds.has(e.id)).map(cloneJson),
    occupant_groups: layout.occupant_groups
      .filter((g) => groupIds.has(g.id))
      .map(cloneJson),
  };
}

function payloadBounds(payload: ClipboardPayload): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
} | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  let any = false;

  const include = (x: number, y: number) => {
    any = true;
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  };

  for (const obstacle of payload.obstacles ?? []) {
    include(obstacle.x, obstacle.y);
    include(obstacle.x + obstacle.width, obstacle.y + obstacle.height);
  }
  for (const space of payload.spaces) {
    for (const [x, y] of space.vertices) include(x, y);
  }
  for (const door of payload.doors) include(door.x, door.y);
  for (const exit of payload.exits) include(exit.x, exit.y);
  for (const group of payload.occupant_groups) {
    if (group.spawn_x != null && group.spawn_y != null) {
      include(group.spawn_x, group.spawn_y);
    }
  }

  if (!any) return null;
  return { minX, minY, maxX, maxY };
}

/** Offset that places the payload's top-left near the given world point. */
export function offsetToWorldPoint(
  payload: ClipboardPayload,
  worldX: number,
  worldY: number,
): { x: number; y: number } {
  const bounds = payloadBounds(payload);
  if (!bounds) return { x: PASTE_OFFSET_M, y: PASTE_OFFSET_M };
  return {
    x: snap(worldX - bounds.minX),
    y: snap(worldY - bounds.minY),
  };
}

function remapId(idMap: Map<string, string>, id: string): string {
  return idMap.get(id) ?? id;
}

export function pastePayload(
  layout: BuildingLayout,
  payload: ClipboardPayload,
  offset: { x: number; y: number },
): { layout: BuildingLayout; selection: Selection } {
  const idMap = new Map<string, string>();

  for (const space of payload.spaces) {
    idMap.set(space.id, uid(space.type === 'stairs' ? 'stairs' : 'room'));
  }
  for (const door of payload.doors) {
    idMap.set(door.id, uid('door'));
  }
  for (const exit of payload.exits) {
    idMap.set(exit.id, uid('exit'));
  }
  for (const group of payload.occupant_groups) {
    idMap.set(group.id, uid('group'));
  }

  const spaces: Space[] = payload.spaces.map((space) => ({
    ...space,
    id: idMap.get(space.id)!,
    name: `${space.name} copy`,
    linked_stair_id: space.linked_stair_id
      ? remapId(idMap, space.linked_stair_id)
      : null,
    vertices: space.vertices.map(
      ([x, y]) => [snap(x + offset.x), snap(y + offset.y)] as Point,
    ),
  }));

  const doors: Door[] = payload.doors.map((door) => ({
    ...door,
    id: idMap.get(door.id)!,
    name: `${door.name} copy`,
    x: snap(door.x + offset.x),
    y: snap(door.y + offset.y),
    connects: [
      remapId(idMap, door.connects[0]),
      remapId(idMap, door.connects[1]),
    ],
  }));

  const exits: Exit[] = payload.exits.map((exit) => ({
    ...exit,
    id: idMap.get(exit.id)!,
    name: `${exit.name} copy`,
    x: snap(exit.x + offset.x),
    y: snap(exit.y + offset.y),
    connected_space_id: remapId(idMap, exit.connected_space_id),
  }));

  const occupant_groups: OccupantGroup[] = payload.occupant_groups.map((group) => {
    const spawn_x =
      group.spawn_x != null ? snap(group.spawn_x + offset.x) : group.spawn_x;
    const spawn_y =
      group.spawn_y != null ? snap(group.spawn_y + offset.y) : group.spawn_y;
    return {
      ...group,
      id: idMap.get(group.id)!,
      name: `${group.name} copy`,
      space_id: remapId(idMap, group.space_id),
      spawn_x,
      spawn_y,
      destination_exit_id: group.destination_exit_id
        ? remapId(idMap, group.destination_exit_id)
        : null,
    };
  });

  const obstacles = (payload.obstacles ?? []).map(o => ({ ...o, id: uid('obstacle'),
    x: Math.max(0, Math.min(layout.width - o.width, snap(o.x + offset.x))),
    y: Math.max(0, Math.min(layout.height - o.height, snap(o.y + offset.y))),
  }));
  const selection: Selection = [
    ...obstacles.map(o => ({ kind: 'obstacle' as const, id: o.id })),
    ...spaces.map((s) => ({ kind: 'space' as const, id: s.id })),
    ...doors.map((d) => ({ kind: 'door' as const, id: d.id })),
    ...exits.map((e) => ({ kind: 'exit' as const, id: e.id })),
    ...occupant_groups.map((g) => ({ kind: 'occupants' as const, id: g.id })),
  ];

  return {
    layout: {
      ...layout,
      spaces: [...layout.spaces, ...spaces],
      obstacles: [...(layout.obstacles ?? []), ...obstacles],
      doors: [...layout.doors, ...doors],
      exits: [...layout.exits, ...exits],
      occupant_groups: [...layout.occupant_groups, ...occupant_groups],
    },
    selection,
  };
}

export function deleteRefs(
  layout: BuildingLayout,
  refs: Selection,
): BuildingLayout {
  if (refs.length === 0) return layout;

  const spaceIds = new Set(
    refs.filter((r) => r.kind === 'space').map((r) => r.id),
  );
  const doorIds = new Set(
    refs.filter((r) => r.kind === 'door').map((r) => r.id),
  );
  const exitIds = new Set(
    refs.filter((r) => r.kind === 'exit').map((r) => r.id),
  );
  const groupIds = new Set(
    refs.filter((r) => r.kind === 'occupants').map((r) => r.id),
  );

  return {
    ...layout,
    obstacles: (layout.obstacles ?? []).filter(o =>
      !refs.some(r => r.kind === 'obstacle' && r.id === o.id)),
    spaces: layout.spaces
      .filter((s) => !spaceIds.has(s.id))
      .map((s) =>
        s.linked_stair_id && spaceIds.has(s.linked_stair_id)
          ? { ...s, linked_stair_id: null }
          : s,
      ),
    doors: layout.doors.filter(
      (d) =>
        !doorIds.has(d.id)
        && !d.connects.some((id) => spaceIds.has(id)),
    ),
    exits: layout.exits.filter(
      (e) =>
        !exitIds.has(e.id)
        && !spaceIds.has(e.connected_space_id),
    ),
    occupant_groups: layout.occupant_groups.filter(
      (g) => !groupIds.has(g.id) && !spaceIds.has(g.space_id),
    ),
    floods: (layout.floods ?? []).filter(
      (f) => !refs.some((r) => r.kind === 'flood' && r.id === f.id),
    ),
    fires: (layout.fires ?? []).filter(
      (f) => !refs.some((r) => r.kind === 'fire' && r.id === f.id),
    ),
  };
}

export function translateSelection(
  layout: BuildingLayout,
  selection: Selection,
  dx: number,
  dy: number,
): BuildingLayout {
  if (dx === 0 && dy === 0) return layout;

  const spaceIds = new Set(
    selection.filter((r) => r.kind === 'space').map((r) => r.id),
  );
  const doorIds = new Set(
    selection.filter((r) => r.kind === 'door').map((r) => r.id),
  );
  const exitIds = new Set(
    selection.filter((r) => r.kind === 'exit').map((r) => r.id),
  );
  const groupIds = new Set(
    selection.filter((r) => r.kind === 'occupants').map((r) => r.id),
  );

  return {
    ...layout,
    obstacles: (layout.obstacles ?? []).map(o =>
      selection.some(r => r.kind === 'obstacle' && r.id === o.id)
        ? { ...o, x: Math.max(0, Math.min(layout.width - o.width, snap(o.x + dx))),
          y: Math.max(0, Math.min(layout.height - o.height, snap(o.y + dy))) } : o),
    spaces: layout.spaces.map((space) => {
      if (!spaceIds.has(space.id)) return space;
      return {
        ...space,
        vertices: space.vertices.map(
          ([x, y]) => [snap(x + dx), snap(y + dy)] as Point,
        ),
      };
    }),
    doors: layout.doors.map((door) => {
      if (!doorIds.has(door.id)) return door;
      return {
        ...door,
        x: snap(door.x + dx),
        y: snap(door.y + dy),
      };
    }),
    exits: layout.exits.map((exit) => {
      if (!exitIds.has(exit.id)) return exit;
      return {
        ...exit,
        x: snap(exit.x + dx),
        y: snap(exit.y + dy),
      };
    }),
    occupant_groups: layout.occupant_groups.map((group) => {
      if (!groupIds.has(group.id)) return group;
      const spawn_x =
        group.spawn_x != null ? snap(group.spawn_x + dx) : group.spawn_x;
      const spawn_y =
        group.spawn_y != null ? snap(group.spawn_y + dy) : group.spawn_y;
      let space_id = group.space_id;
      if (spawn_x != null && spawn_y != null) {
        const translatedSpaces = layout.spaces.map((space) => {
          if (!spaceIds.has(space.id)) return space;
          return {
            ...space,
            vertices: space.vertices.map(
              ([x, y]) => [snap(x + dx), snap(y + dy)] as Point,
            ),
          };
        });
        const host = translatedSpaces.find((s) =>
          pointInPolygon(spawn_x, spawn_y, s.vertices),
        );
        if (host) space_id = host.id;
      }
      return { ...group, spawn_x, spawn_y, space_id };
    }),
    floods: (layout.floods ?? []).map((flood) => {
      if (!selection.some((r) => r.kind === 'flood' && r.id === flood.id)) return flood;
      return {
        ...flood,
        x: Math.max(0, Math.min(layout.width, snap(flood.x + dx))),
        y: Math.max(0, Math.min(layout.height, snap(flood.y + dy))),
      };
    }),
    fires: (layout.fires ?? []).map((fire) => {
      if (!selection.some((r) => r.kind === 'fire' && r.id === fire.id)) return fire;
      return {
        ...fire,
        x: Math.max(0, Math.min(layout.width, snap(fire.x + dx))),
        y: Math.max(0, Math.min(layout.height, snap(fire.y + dy))),
      };
    }),
  };
}
