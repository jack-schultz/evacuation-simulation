import type { OccupantFrameState, SimulationFrame } from '../types/building';

/** Max plausible walk speed (m/s) used to detect stair teleports. */
const TELEPORT_SPEED_MPS = 3.0;
/** Minimum jump distance (m) treated as a teleport regardless of dt. */
const TELEPORT_MIN_M = 3.0;

function lerp(a: number, b: number, alpha: number): number {
  return a + (b - a) * alpha;
}

function lerpRadius(
  a: number | null | undefined,
  b: number | null | undefined,
  alpha: number,
): number | null | undefined {
  if (a == null && b == null) return a;
  if (a == null) return b;
  if (b == null) return a;
  return lerp(a, b, alpha);
}

function distance(ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax;
  const dy = by - ay;
  return Math.hypot(dx, dy);
}

function isTeleport(
  a: OccupantFrameState,
  b: OccupantFrameState,
  dt: number,
): boolean {
  // Directed stair climbs already emit intermediate positions — don't snap.
  if (a.status === 'climbing' || b.status === 'climbing') return false;
  if (a.climb_progress != null || b.climb_progress != null) return false;
  const limit = Math.max(TELEPORT_MIN_M, TELEPORT_SPEED_MPS * Math.max(dt, 0));
  return distance(a.x, a.y, b.x, b.y) > limit;
}

function interpolateOccupant(
  a: OccupantFrameState,
  b: OccupantFrameState,
  alpha: number,
  dt: number,
): OccupantFrameState {
  const teleport = isTeleport(a, b, dt);
  const posAlpha = teleport ? (alpha < 0.5 ? 0 : 1) : alpha;
  const meta = alpha < 1 ? a : b;
  const climbA = a.climb_progress;
  const climbB = b.climb_progress;
  let climb_progress: number | null | undefined = meta.climb_progress;
  if (climbA != null && climbB != null) {
    climb_progress = lerp(climbA, climbB, alpha);
  } else if (climbA != null || climbB != null) {
    climb_progress = climbA ?? climbB;
  }
  return {
    id: a.id,
    x: lerp(a.x, b.x, posAlpha),
    y: lerp(a.y, b.y, posAlpha),
    status: meta.status,
    deceased: meta.deceased ?? false,
    group_id: meta.group_id,
    floor_id: meta.floor_id,
    route_index: meta.route_index ?? 0,
    climb_progress,
    path_preview: meta.path_preview ?? [],
  };
}

/**
 * Build a display frame at continuous simulation time `t` by lerping between
 * the recorded frames that bracket `t`.
 */
export function interpolateFrame(
  frames: SimulationFrame[],
  t: number,
): SimulationFrame | null {
  if (frames.length === 0) return null;

  if (t <= frames[0].t) {
    return frames[0];
  }

  const last = frames[frames.length - 1];
  if (t >= last.t) {
    return last;
  }

  let i = 0;
  while (i < frames.length - 1 && frames[i + 1].t < t) {
    i += 1;
  }

  const a = frames[i];
  const b = frames[i + 1];
  const span = b.t - a.t;
  const alpha = span > 0 ? (t - a.t) / span : 0;
  const dt = span;

  const byId = new Map(b.occupants.map((o) => [o.id, o]));
  const seen = new Set<string>();
  const occupants: OccupantFrameState[] = [];

  for (const from of a.occupants) {
    seen.add(from.id);
    const to = byId.get(from.id);
    if (!to) {
      if (alpha < 1) occupants.push(from);
      continue;
    }
    occupants.push(interpolateOccupant(from, to, alpha, dt));
  }

  if (alpha >= 1) {
    for (const to of b.occupants) {
      if (!seen.has(to.id)) occupants.push(to);
    }
  }

  return {
    t,
    flood_radius_m: lerpRadius(a.flood_radius_m, b.flood_radius_m, alpha),
    flood_rooms: alpha < 0.5 ? (a.flood_rooms ?? []) : (b.flood_rooms ?? []),
    fire_radius_m: lerpRadius(a.fire_radius_m, b.fire_radius_m, alpha),
    fire_floors: alpha < 0.5 ? (a.fire_floors ?? []) : (b.fire_floors ?? []),
    smoke_floors: alpha < 0.5 ? (a.smoke_floors ?? []) : (b.smoke_floors ?? []),
    smoke_rooms: alpha < 0.5 ? (a.smoke_rooms ?? []) : (b.smoke_rooms ?? []),
    occupants,
  };
}

/** Index of the recorded frame with the largest `t` that is still ≤ `simTime`. */
export function frameIndexAt(frames: SimulationFrame[], simTime: number): number {
  if (frames.length === 0) return 0;
  let i = 0;
  while (i < frames.length - 1 && frames[i + 1].t <= simTime) {
    i += 1;
  }
  return i;
}
