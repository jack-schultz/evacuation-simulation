import { Group, Rect, Text } from 'react-konva';
import type { BuildingLayout, ObjectRef, Selection } from '../../../types/building';
import { isRefSelected } from '../../../types/editor';
import { SCALE } from '../../../utils';
import { moveExit } from '../../../exitPlacement';
import type {
  DragPropsFn,
  HandleObjectClickFn,
  OpenObjectContextMenuFn,
} from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  selected: Selection;
  interactive: boolean;
  congestedIds?: Set<string>;
  onObjectClick: HandleObjectClickFn;
  onHover: (ref: ObjectRef | null) => void;
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
  onObjectContextMenu: OpenObjectContextMenuFn;
}

export function OpeningsLayer({
  layout,
  selected,
  interactive,
  congestedIds,
  onObjectClick,
  onHover,
  onChange,
  dragProps,
  onObjectContextMenu,
}: Props) {
  return (
    <>
      {layout.doors.map((d) => {
        const active = isRefSelected(selected, { kind: 'door', id: d.id });
        const ref: ObjectRef = { kind: 'door', id: d.id };
        return (
          <Rect
            key={d.id}
            x={d.x * SCALE}
            y={d.y * SCALE}
            offsetX={6}
            offsetY={6}
            {...dragProps(
              ref,
              (x, y) => {
                onChange({
                  ...layout,
                  doors: layout.doors.map((door) =>
                    door.id === d.id ? { ...door, x, y } : door,
                  ),
                });
              },
              0,
              0,
              { x: d.x, y: d.y },
            )}
            width={12}
            height={12}
            fill={congestedIds?.has(d.id) ? '#ef4444' : '#f59e0b'}
            stroke={active ? '#2563eb' : '#92400e'}
            strokeWidth={active ? 2 : 1}
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
          />
        );
      })}

      {layout.exits.map((ex) => {
        const active = isRefSelected(selected, { kind: 'exit', id: ex.id });
        const ref: ObjectRef = { kind: 'exit', id: ex.id };
        return (
          <Group
            key={ex.id}
            x={ex.x * SCALE}
            y={ex.y * SCALE}
            onClick={(e) => onObjectClick(ref, e)}
            onContextMenu={(e) => onObjectContextMenu(ref, e)}
            {...dragProps(
              ref,
              (x, y) => {
                onChange(moveExit(layout, ex.id, x, y));
              },
              0,
              0,
              { x: ex.x, y: ex.y },
            )}
            onMouseEnter={(event) => {
              onHover(ref);
              if (interactive) event.target.getStage()!.container().style.cursor = 'grab';
            }}
            onMouseLeave={(event) => {
              onHover(null);
              event.target.getStage()!.container().style.cursor = '';
            }}
          >
            <Rect
              x={-10}
              y={-10}
              width={20}
              height={20}
              fill={congestedIds?.has(ex.id) ? '#ef4444' : '#22c55e'}
              stroke={active ? '#2563eb' : '#166534'}
              strokeWidth={2}
            />
            <Text text="EXIT" x={-14} y={12} fontSize={10} fill="#166534" listening={false} />
          </Group>
        );
      })}
    </>
  );
}
