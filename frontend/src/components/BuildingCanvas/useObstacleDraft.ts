import { useState } from 'react';
import type Konva from 'konva';
import type { BuildingLayout, EditorTool, Selection } from '../../types/building';
import { SCALE, snap, uid } from '../../utils';

type Point = { x: number; y: number };
export function useObstacleDraft(layout: BuildingLayout, tool: EditorTool, interactive: boolean,
  activeFloorId: string, onChange: (layout: BuildingLayout) => void,
  onSelect: (selection: Selection) => void) {
  const [start, setStart] = useState<Point | null>(null);
  const [end, setEnd] = useState<Point | null>(null);
  const cancel = () => { setStart(null); setEnd(null); };
  const context = tool + ':' + activeFloorId + ':' + interactive;
  const [draftContext, setDraftContext] = useState(context);
  if (draftContext !== context) {
    setDraftContext(context);
    setStart(null);
    setEnd(null);
  }
  const enabled = interactive && tool === 'obstacle';
  const point = (event: Konva.KonvaEventObject<MouseEvent>): Point | null => {
    const stage = event.target.getStage();
    const pointer = stage?.getPointerPosition();
    if (!stage || !pointer) return null;
    const local = stage.getAbsoluteTransform().copy().invert().point(pointer);
    return {
      x: Math.max(0, Math.min(layout.width, snap(local.x / SCALE))),
      y: Math.max(0, Math.min(layout.height, snap(local.y / SCALE))),
    };
  };
  const rectangle = (a: Point, b: Point) => ({
    x: Math.min(a.x, b.x), y: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x), height: Math.abs(a.y - b.y),
  });
  return {
    preview: enabled && start && end ? rectangle(start, end) : null,
    cancel,
    onMouseDown: (event: Konva.KonvaEventObject<MouseEvent>) => {
      if (!enabled) return false;
      if (event.evt.button !== 0) { cancel(); return true; }
      const p = point(event);
      setStart(p); setEnd(p);
      return true;
    },
    onMouseMove: (event: Konva.KonvaEventObject<MouseEvent>) => {
      if (!enabled || !start) return false;
      if (!(event.evt.buttons & 1)) { cancel(); return true; }
      setEnd(point(event));
      return true;
    },
    onMouseUp: (event: Konva.KonvaEventObject<MouseEvent>) => {
      if (!enabled || !start) return;
      const p = point(event);
      if (p) {
        const rect = rectangle(start, p);
        if (rect.width >= 0.5 && rect.height >= 0.5) {
          const id = uid('obstacle');
          onChange({ ...layout, obstacles: [...(layout.obstacles ?? []),
            { ...rect, id, name: 'Obstacle', floor_id: activeFloorId }] });
          onSelect([{ kind: 'obstacle', id }]);
        }
      }
      cancel();
    },
  };
}
