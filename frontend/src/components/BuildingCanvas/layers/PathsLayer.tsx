import { useMemo } from 'react';
import { Line } from 'react-konva';
import type { OccupantFrameState, OccupantResult } from '../../../types/building';
import { SCALE } from '../../../utils';

interface Props {
  routeOccupants: OccupantResult[];
  liveOccupants: OccupantFrameState[];
  activeFloorId: string;
}

const PATH_COLORS = ['#2563eb', '#7c3aed', '#0891b2', '#c026d3', '#4f46e5'];

const HIDDEN_STATUSES = new Set(['evacuated', 'trapped']);

function remainingFloorPath(
  live: OccupantFrameState,
  result: OccupantResult,
  activeFloorId: string,
): number[] | null {
  const pts = result.route_points;
  if (!pts || pts.length < 1) return null;

  const floors = result.route_floors ?? [];
  const routeIndex = Math.max(0, live.route_index ?? 0);

  const poly: number[] = [live.x * SCALE, live.y * SCALE];
  let added = 0;

  for (let i = routeIndex; i < pts.length; i++) {
    const floor = floors[i] ?? 'floor-0';
    if (floor !== activeFloorId) {
      // Stair / floor hop — stop so we don't draw a cross-floor chord.
      break;
    }
    const [x, y] = pts[i];
    poly.push(x * SCALE, y * SCALE);
    added += 1;
  }

  // Need the live position plus at least one remaining waypoint.
  if (added < 1 || poly.length < 4) return null;
  return poly;
}

export function PathsLayer({ routeOccupants, liveOccupants, activeFloorId }: Props) {
  const paths = useMemo(() => {
    const byId = new Map(routeOccupants.map((o) => [o.id, o]));
    const out: { key: string; points: number[] }[] = [];

    for (const live of liveOccupants) {
      if (HIDDEN_STATUSES.has(live.status)) continue;
      if ((live.floor_id ?? 'floor-0') !== activeFloorId) continue;

      const result = byId.get(live.id);
      if (!result) continue;

      const points = remainingFloorPath(live, result, activeFloorId);
      if (!points) continue;

      out.push({ key: live.id, points });
    }
    return out;
  }, [routeOccupants, liveOccupants, activeFloorId]);

  if (!paths.length) return null;

  return (
    <>
      {paths.map((path, i) => (
        <Line
          key={path.key}
          points={path.points}
          stroke={PATH_COLORS[i % PATH_COLORS.length]}
          strokeWidth={2}
          opacity={0.55}
          dash={[8, 6]}
          lineCap="round"
          lineJoin="round"
          listening={false}
        />
      ))}
    </>
  );
}
