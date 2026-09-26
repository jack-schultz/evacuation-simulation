import { useMemo } from 'react';
import { Line } from 'react-konva';
import type { OccupantResult } from '../../../types/building';
import { SCALE } from '../../../utils';

interface Props {
  occupants: OccupantResult[];
}

const PATH_COLORS = ['#2563eb', '#7c3aed', '#0891b2', '#c026d3', '#4f46e5'];

function routeKey(points: [number, number][]): string {
  return points.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join('|');
}

export function PathsLayer({ occupants }: Props) {
  const paths = useMemo(() => {
    const seen = new Set<string>();
    const unique: { key: string; points: number[] }[] = [];
    for (const occ of occupants) {
      const pts = occ.route_points;
      if (!pts || pts.length < 2) continue;
      const key = routeKey(pts);
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push({
        key,
        points: pts.flatMap(([x, y]) => [x * SCALE, y * SCALE]),
      });
    }
    return unique;
  }, [occupants]);

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
