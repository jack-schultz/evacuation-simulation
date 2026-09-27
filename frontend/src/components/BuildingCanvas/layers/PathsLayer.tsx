import { useMemo } from 'react';
import { Line } from 'react-konva';
import type { BuildingLayout, OccupantResult } from '../../../types/building';
import { SCALE } from '../../../utils';
import { floorIdForRouteNode, routeSegmentsForFloor } from './pathFloorFilter';

interface Props {
  occupants: OccupantResult[];
  layout: BuildingLayout;
  activeFloorId: string;
  showAllFloors?: boolean;
}

const PATH_COLORS = ['#2563eb', '#7c3aed', '#0891b2', '#c026d3', '#4f46e5'];

function routeKey(points: [number, number][]): string {
  return points.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join('|');
}

export function PathsLayer({
  occupants,
  layout,
  activeFloorId,
  showAllFloors = false,
}: Props) {
  const paths = useMemo(() => {
    const seen = new Set<string>();
    const unique: { key: string; points: number[] }[] = [];
    for (const occ of occupants) {
      const pts = occ.route_points;
      const nodes = occ.route_node_ids;
      if (!pts || pts.length < 2 || !nodes?.length) continue;
      const floors = nodes.map((id) => floorIdForRouteNode(id, layout, occ.group_id));
      for (const segment of routeSegmentsForFloor(pts, floors, activeFloorId, showAllFloors)) {
        const key = routeKey(segment);
        if (seen.has(key)) continue;
        seen.add(key);
        unique.push({
          key,
          points: segment.flatMap(([x, y]) => [x * SCALE, y * SCALE]),
        });
      }
    }
    return unique;
  }, [occupants, layout, activeFloorId, showAllFloors]);

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
