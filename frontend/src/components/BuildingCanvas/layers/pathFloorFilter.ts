import type { BuildingLayout } from '../../../types/building.ts';
import { entityFloorId } from '../../../layout/emptyLayout.ts';

/** Resolve the storey for a nav-graph node id using the building layout. */
export function floorIdForRouteNode(
  nodeId: string,
  layout: BuildingLayout,
  groupId?: string,
): string | null {
  if (nodeId.startsWith('space:')) {
    const space = layout.spaces.find((s) => s.id === nodeId.slice('space:'.length));
    return space ? entityFloorId(space) : null;
  }
  if (nodeId.startsWith('door:')) {
    const door = layout.doors.find((d) => d.id === nodeId.slice('door:'.length));
    return door ? entityFloorId(door) : null;
  }
  if (nodeId.startsWith('exit:')) {
    const exit = layout.exits.find((e) => e.id === nodeId.slice('exit:'.length));
    return exit ? entityFloorId(exit) : null;
  }
  if (nodeId.startsWith('waypoint:')) {
    const spaceId = nodeId.slice('waypoint:'.length).split(':')[0];
    const space = layout.spaces.find((s) => s.id === spaceId);
    return space ? entityFloorId(space) : null;
  }
  if (nodeId.startsWith('spawn:')) {
    const group = layout.occupant_groups.find((g) => g.id === groupId);
    return group ? entityFloorId(group) : null;
  }
  return null;
}

/** Contiguous same-floor polylines from a route (breaks at stair / floor changes). */
export function routeSegmentsForFloor(
  points: [number, number][],
  floors: (string | null)[],
  activeFloorId: string,
  showAllFloors = false,
): [number, number][][] {
  const segments: [number, number][][] = [];
  let current: [number, number][] = [];
  let currentFloor: string | null = null;

  const flush = () => {
    if (current.length >= 2) segments.push(current);
    current = [];
    currentFloor = null;
  };

  const n = Math.min(points.length, floors.length);
  for (let i = 0; i < n; i++) {
    const floor = floors[i];
    const include = floor != null && (showAllFloors || floor === activeFloorId);
    if (!include) {
      flush();
      continue;
    }
    if (currentFloor != null && floor !== currentFloor) {
      flush();
    }
    current.push(points[i]);
    currentFloor = floor;
  }
  flush();
  return segments;
}
