import { Circle, Group, Text } from 'react-konva';
import type { BuildingLayout, OccupantFrameState, SelectedRef } from '../../../types/building';
import { SCALE, snap } from '../../../utils';
import { spaceCentroid, spaceContaining } from '../geometryHelpers';
import type { DragPropsFn } from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  selected: SelectedRef;
  interactive: boolean;
  occupants: OccupantFrameState[];
  occupantRadiusPx: number;
  onSelect: (ref: SelectedRef) => void;
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
}

export function OccupantsLayer({
  layout,
  selected,
  interactive,
  occupants,
  occupantRadiusPx,
  onSelect,
  onChange,
  dragProps,
}: Props) {
  const isSelected = (kind: string, id: string) =>
    selected?.kind === kind && selected.id === id;

  return (
    <>
      {layout.occupant_groups.map((g) => {
        const space = layout.spaces.find((s) => s.id === g.space_id);
        if (!space) return null;
        const [centerX, centerY] = spaceCentroid(space.vertices);
        const sx = g.spawn_x ?? centerX;
        const sy = g.spawn_y ?? centerY;
        const cx = sx * SCALE;
        const cy = sy * SCALE;
        return (
          <Group
            key={g.id}
            x={cx}
            y={cy}
            {...dragProps({ kind: 'occupants', id: g.id }, () => {})}
            onDragEnd={(e) => {
              const x = snap(e.target.x() / SCALE);
              const y = snap(e.target.y() / SCALE);
              const spaceId = spaceContaining(layout, x, y);
              e.target.position({ x: cx, y: cy });
              e.target.getStage()!.container().style.cursor = '';
              e.cancelBubble = true;
              if (spaceId) {
                onChange({
                  ...layout,
                  occupant_groups: layout.occupant_groups.map((group) =>
                    group.id === g.id
                      ? { ...group, space_id: spaceId, spawn_x: x, spawn_y: y }
                      : group,
                  ),
                });
              }
            }}
            onClick={() => interactive && onSelect({ kind: 'occupants', id: g.id })}
          >
            <Circle
              radius={14}
              fill={isSelected('occupants', g.id) ? '#7c3aed' : '#8b5cf6'}
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
