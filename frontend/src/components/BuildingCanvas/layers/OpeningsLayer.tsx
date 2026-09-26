import { Group, Rect, Text } from 'react-konva';
import type { BuildingLayout, SelectedRef } from '../../../types/building';
import { SCALE } from '../../../utils';
import { moveExit } from '../../../exitPlacement';
import type { DragPropsFn } from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  selected: SelectedRef;
  interactive: boolean;
  congestedIds?: Set<string>;
  onSelect: (ref: SelectedRef) => void;
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
}

export function OpeningsLayer({
  layout,
  selected,
  interactive,
  congestedIds,
  onSelect,
  onChange,
  dragProps,
}: Props) {
  const isSelected = (kind: string, id: string) =>
    selected?.kind === kind && selected.id === id;

  return (
    <>
      {layout.doors.map((d) => (
        <Rect
          key={d.id}
          x={d.x * SCALE}
          y={d.y * SCALE}
          offsetX={6}
          offsetY={6}
          {...dragProps({ kind: 'door', id: d.id }, (x, y) => {
            onChange({
              ...layout,
              doors: layout.doors.map((door) =>
                door.id === d.id ? { ...door, x, y } : door,
              ),
            });
          })}
          width={12}
          height={12}
          fill={congestedIds?.has(d.id) ? '#ef4444' : '#f59e0b'}
          stroke={isSelected('door', d.id) ? '#2563eb' : '#92400e'}
          strokeWidth={isSelected('door', d.id) ? 2 : 1}
          onClick={() => interactive && onSelect({ kind: 'door', id: d.id })}
        />
      ))}

      {layout.exits.map((ex) => (
        <Group
          key={ex.id}
          x={ex.x * SCALE}
          y={ex.y * SCALE}
          onClick={() => interactive && onSelect({ kind: 'exit', id: ex.id })}
          {...dragProps({ kind: 'exit', id: ex.id }, (x, y) => {
            onChange(moveExit(layout, ex.id, x, y));
          })}
        >
          <Rect
            x={-10}
            y={-10}
            width={20}
            height={20}
            fill={congestedIds?.has(ex.id) ? '#ef4444' : '#22c55e'}
            stroke={isSelected('exit', ex.id) ? '#2563eb' : '#166534'}
            strokeWidth={2}
          />
          <Text text="EXIT" x={-14} y={12} fontSize={10} fill="#166534" listening={false} />
        </Group>
      ))}
    </>
  );
}
