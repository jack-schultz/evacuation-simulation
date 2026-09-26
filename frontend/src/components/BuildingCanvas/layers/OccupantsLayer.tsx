import { Circle, Group, Text } from 'react-konva';
import type {
  BuildingLayout,
  ObjectRef,
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
  interactive: boolean;
  occupants: OccupantFrameState[];
  occupantRadiusPx: number;
  activeFloorId: string;
  onObjectClick: HandleObjectClickFn;
  onHover: (ref: ObjectRef | null) => void;
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
  onObjectContextMenu: OpenObjectContextMenuFn;
}

export function OccupantsLayer({
  layout,
  selected,
  interactive,
  occupants,
  occupantRadiusPx,
  activeFloorId,
  onObjectClick,
  onHover,
  onChange,
  dragProps,
  onObjectContextMenu,
}: Props) {
  return (
    <>
      {layout.occupant_groups
        .filter((g) => (g.floor_id ?? 'floor-0') === activeFloorId)
        .map((g) => {
        const space = layout.spaces.find((s) => s.id === g.space_id);
        if (!space) return null;
        const [centerX, centerY] = spaceCentroid(space.vertices);
        const sx = g.spawn_x ?? centerX;
        const sy = g.spawn_y ?? centerY;
        const active = isRefSelected(selected, { kind: 'occupants', id: g.id });
        const ref: ObjectRef = { kind: 'occupants', id: g.id };
        return (
          <Group
            key={g.id}
            x={sx * SCALE}
            y={sy * SCALE}
            {...dragProps(
              ref,
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
            onClick={(e) => onObjectClick(ref, e)}
            onContextMenu={(e) => onObjectContextMenu(ref, e)}
            onMouseEnter={(event) => {
              onHover(ref);
              if (interactive) event.target.getStage()!.container().style.cursor = 'grab';
            }}
            onMouseLeave={(event) => {
              onHover(null);
              event.target.getStage()!.container().style.cursor = '';
            }}
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
        .filter(
          (o) =>
            o.status !== 'evacuated' &&
            (o.floor_id ?? 'floor-0') === activeFloorId,
        )
        .map((o) => (
          <Circle
            key={o.id}
            x={o.x * SCALE}
            y={o.y * SCALE}
            radius={occupantRadiusPx}
            opacity={o.status === 'climbing' ? 0.55 + 0.45 * (o.climb_progress ?? 0) : 1}
            fill={
              o.status === 'trapped'
                ? '#7c3aed'
                : o.status === 'climbing'
                  ? '#d97706'
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
