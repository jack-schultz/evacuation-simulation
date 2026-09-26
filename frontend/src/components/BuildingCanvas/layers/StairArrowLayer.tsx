import { Arrow, Group, Text } from 'react-konva';
import type { BuildingLayout, Floor, Space } from '../../../types/building';
import { entityFloorId, ensureFloors } from '../../../layout/emptyLayout';
import { SCALE, polygonBBox } from '../../../utils';
import { spaceCentroid } from '../geometryHelpers';

interface Props {
  layout: BuildingLayout;
  activeFloorId: string;
}

function longAxis(space: Space): [[number, number], [number, number]] {
  const box = polygonBBox(space.vertices);
  const [cx, cy] = spaceCentroid(space.vertices);
  if (box.width >= box.height) {
    return [
      [box.x + 0.15 * box.width, cy],
      [box.x + 0.85 * box.width, cy],
    ];
  }
  return [
    [cx, box.y + 0.15 * box.height],
    [cx, box.y + 0.85 * box.height],
  ];
}

function floorMap(layout: BuildingLayout): Record<string, Floor> {
  return Object.fromEntries(ensureFloors(layout).map((f) => [f.id, f]));
}

export function StairArrowLayer({ layout, activeFloorId }: Props) {
  const floors = floorMap(layout);
  const stairs = layout.spaces.filter(
    (s) => s.type === 'stairs' && entityFloorId(s) === activeFloorId,
  );

  return (
    <>
      {stairs.map((space) => {
        const partner = space.linked_stair_id
          ? layout.spaces.find((s) => s.id === space.linked_stair_id)
          : null;
        const [a, b] = longAxis(space);
        let from = a;
        let to = b;
        let label = 'Link a floor';
        if (partner) {
          const elev = floors[entityFloorId(space)]?.elevation_m ?? 0;
          const partnerElev = floors[entityFloorId(partner)]?.elevation_m ?? 0;
          const partnerFloor = floors[entityFloorId(partner)];
          if (elev >= partnerElev) {
            from = a;
            to = b;
            label = `Down to ${partnerFloor?.name ?? 'lower'}`;
          } else {
            from = b;
            to = a;
            label = `Up to ${partnerFloor?.name ?? 'upper'}`;
          }
        }
        const midX = ((from[0] + to[0]) / 2) * SCALE;
        const midY = ((from[1] + to[1]) / 2) * SCALE;
        return (
          <Group key={`stair-arrow-${space.id}`} listening={false}>
            <Arrow
              points={[
                from[0] * SCALE,
                from[1] * SCALE,
                to[0] * SCALE,
                to[1] * SCALE,
              ]}
              pointerLength={14}
              pointerWidth={14}
              fill={partner ? '#b45309' : '#94a3b8'}
              stroke={partner ? '#b45309' : '#94a3b8'}
              strokeWidth={3}
              opacity={0.85}
            />
            <Text
              x={midX - 55}
              y={midY - 18}
              width={110}
              align="center"
              text={label}
              fontSize={11}
              fill={partner ? '#92400e' : '#64748b'}
              fontStyle="bold"
            />
          </Group>
        );
      })}
    </>
  );
}
