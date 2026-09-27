import { Rect } from 'react-konva';
import type { BuildingLayout, ObjectRef, Selection } from '../../../types/building';
import { isRefSelected } from '../../../types/editor';
import { SCALE } from '../../../utils';
import type { DragPropsFn, HandleObjectClickFn, OpenObjectContextMenuFn } from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  selected: Selection;
  activeFloorId: string;
  showAllFloors: boolean;
  onChange: (layout: BuildingLayout) => void;
  onObjectClick: HandleObjectClickFn;
  onObjectContextMenu: OpenObjectContextMenuFn;
  onHover: (ref: ObjectRef | null) => void;
  dragProps: DragPropsFn;
}

export function ObstacleLayer({ layout, selected, activeFloorId, showAllFloors,
  onChange, onObjectClick, onObjectContextMenu, onHover, dragProps }: Props) {
  return <>{(layout.obstacles ?? []).filter(o =>
    showAllFloors || (o.floor_id ?? 'floor-0') === activeFloorId).map(o => {
    const ref: ObjectRef = { kind: 'obstacle', id: o.id };
    const active = isRefSelected(selected, ref);
    return <Rect key={o.id} x={o.x * SCALE} y={o.y * SCALE}
      width={o.width * SCALE} height={o.height * SCALE}
      fill="#64748b" stroke={active ? '#2563eb' : '#334155'} strokeWidth={active ? 3 : 2}
      {...dragProps(ref, (x, y) => onChange({ ...layout,
        obstacles: (layout.obstacles ?? []).map(item => item.id === o.id ? { ...item, x, y } : item),
      }), o.width, o.height, { x: o.x, y: o.y })}
      onClick={event => onObjectClick(ref, event)}
      onContextMenu={event => onObjectContextMenu(ref, event)}
      onMouseEnter={() => onHover(ref)} onMouseLeave={() => onHover(null)} />;
  })}</>;
}
