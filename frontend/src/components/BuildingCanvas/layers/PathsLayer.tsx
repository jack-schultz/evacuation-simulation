import { Fragment, useMemo } from 'react';
import { Arrow, Line } from 'react-konva';
import type { OccupantFrameState, OccupantResult } from '../../../types/building';
import { SCALE } from '../../../utils';

interface Props {
  routeOccupants: OccupantResult[];
  liveOccupants: OccupantFrameState[];
  activeFloorId: string;
}

const PATH_COLORS = ['#2563eb', '#7c3aed', '#0891b2', '#c026d3', '#4f46e5'];

const HIDDEN_STATUSES = new Set(['evacuated', 'trapped']);

function walkIndexes(result: OccupantResult): number[] {
  if (result.route_point_indexes && result.route_point_indexes.length === result.route_points.length) {
    return result.route_point_indexes;
  }
  // Legacy payloads: treat every point as a walk vertex in order.
  return result.route_points.map((_, i) => i);
}

function remainingFloorPath(
  live: OccupantFrameState,
  result: OccupantResult,
  activeFloorId: string,
): number[] | null {
  const pts = result.route_points;
  if (!pts || pts.length < 1) return null;

  const floors = result.route_floors ?? [];
  const indexes = walkIndexes(result);
  const routeIndex = Math.max(0, live.route_index ?? 0);

  const poly: number[] = [live.x * SCALE, live.y * SCALE];
  let added = 0;

  for (let j = 0; j < pts.length; j++) {
    // Remaining walk waypoints ahead of the current route bookkeeping node.
    if (indexes[j] <= routeIndex) continue;
    const floor = floors[j] ?? 'floor-0';
    if (floor !== activeFloorId) {
      break;
    }
    const [x, y] = pts[j];
    poly.push(x * SCALE, y * SCALE);
    added += 1;
  }

  if (added < 1 || poly.length < 4) return null;
  return poly;
}

function tipArrow(points: number[]): number[] | null {
  const n = points.length;
  if (n < 4) return null;
  const x2 = points[n - 2];
  const y2 = points[n - 1];
  const x1 = points[n - 4];
  const y1 = points[n - 3];
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy);
  if (len < 1e-6) return null;
  const tip = Math.min(14, len * 0.35);
  const sx = x2 - (dx / len) * tip;
  const sy = y2 - (dy / len) * tip;
  return [sx, sy, x2, y2];
}

export function PathsLayer({ routeOccupants, liveOccupants, activeFloorId }: Props) {
  const paths = useMemo(() => {
    const byId = new Map(routeOccupants.map((o) => [o.id, o]));
    const out: { key: string; points: number[]; color: string }[] = [];

    for (const live of liveOccupants) {
      if (HIDDEN_STATUSES.has(live.status)) continue;
      if ((live.floor_id ?? 'floor-0') !== activeFloorId) continue;

      const result = byId.get(live.id);
      if (!result) continue;

      const points = remainingFloorPath(live, result, activeFloorId);
      if (!points) continue;

      const color = PATH_COLORS[out.length % PATH_COLORS.length];
      out.push({ key: live.id, points, color });
    }
    return out;
  }, [routeOccupants, liveOccupants, activeFloorId]);

  if (!paths.length) return null;

  return (
    <>
      {paths.map((path) => {
        const arrow = tipArrow(path.points);
        return (
          <Fragment key={path.key}>
            <Line
              points={path.points}
              stroke={path.color}
              strokeWidth={2}
              opacity={0.55}
              dash={[8, 6]}
              lineCap="round"
              lineJoin="round"
              listening={false}
            />
            {arrow && (
              <Arrow
                points={arrow}
                stroke={path.color}
                fill={path.color}
                opacity={0.75}
                strokeWidth={2}
                pointerLength={8}
                pointerWidth={7}
                listening={false}
              />
            )}
          </Fragment>
        );
      })}
    </>
  );
}
