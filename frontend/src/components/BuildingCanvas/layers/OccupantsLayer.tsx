import { Circle, Group, Text } from 'react-konva';
import type {
  BuildingLayout,
  OccupantFrameState,
  Selection,
} from '../../../types/building';
import { isRefSelected } from '../../../types/editor';
import { SCALE } from '../../../utils';
import { spaceCentroid, spaceContaining } from '../geometryHelpers';
import type {
  DragPropsFn,
  HandleObjectClickFn,
  OpenObjectContextMenuFn,
} from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  selected: Selection;
  occupants: OccupantFrameState[];
  occupantRadiusPx: number;
  onObjectClick: HandleObjectClickFn;
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
  onObjectContextMenu: OpenObjectContextMenuFn;
}

export function OccupantsLayer({
  layout,
  selected,
  occupants,
  occupantRadiusPx,
  onObjectClick,
  onChange,
  dragProps,
  onObjectContextMenu,
}: Props) {
  return (
    <>
      {layout.occupant_groups.map((g) => {
        const space = layout.spaces.find((s) => s.id === g.space_id);
        if (!space) return null;
        const [centerX, centerY] = spaceCentroid(space.vertices);
        const sx = g.spawn_x ?? centerX;
        const sy = g.spawn_y ?? centerY;
        const active = isRefSelected(selected, { kind: 'occupants', id: g.id });
        return (
          <Group
            key={g.id}
            x={sx * SCALE}
            y={sy * SCALE}
            {...dragProps(
              { kind: 'occupants', id: g.id },
              (x, y) => {
                const spaceId = spaceContaining(layout, x, y);
                if (!spaceId) return;
                onChange({
                  ...layout,
                  occupant_groups: layout.occupant_groups.map((group) =>
                    group.id === g.id
                      ? { ...group, space_id: spaceId, spawn_x: x, spawn_y: y }
                      : group,
                  ),
                });
              },
              0,
              0,
              { x: sx, y: sy },
              {
                validate: (x, y) => spaceContaining(layout, x, y) != null,
              },
            )}
            onClick={(e) => onObjectClick({ kind: 'occupants', id: g.id }, e)}
            onContextMenu={(e) =>
              onObjectContextMenu({ kind: 'occupants', id: g.id }, e)
            }
          >
            <Circle
              radius={14}
              fill={active ? '#7c3aed' : '#8b5cf6'}
              opacity={occupants.length ? 0.25 : 0.9}
            />
            <Text
              text={String(g.count)}
              x={-10}
              y={-5}
              width={20}
              align="center"
              fontSize={11}
              fill="#fff"
              listening={false}
            />
          </Group>
        );
      })}

      {occupants
        .filter((o) => o.status !== 'evacuated')
        .map((o) => (
          <Circle
            key={o.id}
            x={o.x * SCALE}
            y={o.y * SCALE}
            radius={occupantRadiusPx}
            fill={
              o.status === 'trapped'
                ? '#7c3aed'
                : o.status === 'waiting'
                  ? '#ef4444'
                  : '#2563eb'
            }
            listening={false}
          />
        ))}
    </>
  );
}
