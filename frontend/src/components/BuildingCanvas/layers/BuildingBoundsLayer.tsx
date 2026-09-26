import { Line, Rect } from 'react-konva';
import type Konva from 'konva';
import type { BuildingLayout, EditorTool } from '../../../types/building';
import { SCALE } from '../../../utils';
import {
  clampBuildingSize,
  sizeFromHandleDrag,
  type BuildingResizeHandle,
} from '../buildingBounds';

const HANDLE = 10;
const HALF = HANDLE / 2;

const HANDLES: {
  id: BuildingResizeHandle;
  cursor: string;
  x: (w: number, h: number) => number;
  y: (w: number, h: number) => number;
}[] = [
  { id: 'e', cursor: 'ew-resize', x: (w) => w, y: (_w, h) => h / 2 },
  { id: 's', cursor: 'ns-resize', x: (w) => w / 2, y: (_w, h) => h },
  { id: 'ne', cursor: 'nesw-resize', x: (w) => w, y: () => 0 },
  { id: 'se', cursor: 'nwse-resize', x: (w) => w, y: (_w, h) => h },
  { id: 'sw', cursor: 'nesw-resize', x: () => 0, y: (_w, h) => h },
];

interface Props {
  layout: BuildingLayout;
  widthM: number;
  heightM: number;
  tool: EditorTool;
  interactive: boolean;
  onPreview: (size: { width: number; height: number } | null) => void;
  onCommit: (size: { width: number; height: number }) => void;
}

export function BuildingBoundsLayer({
  layout,
  widthM,
  heightM,
  tool,
  interactive,
  onPreview,
  onCommit,
}: Props) {
  const widthPx = widthM * SCALE;
  const heightPx = heightM * SCALE;
  const showHandles = interactive && tool === 'select';

  const applyPointer = (handle: BuildingResizeHandle, node: Konva.Node) => {
    const stage = node.getStage();
    const pointer = stage?.getPointerPosition();
    if (!stage || !pointer) return null;
    const transform = stage.getAbsoluteTransform().copy().invert();
    const local = transform.point(pointer);
    const raw = sizeFromHandleDrag(
      handle,
      local.x / SCALE,
      local.y / SCALE,
      widthM,
      heightM,
    );
    return clampBuildingSize(raw.width, raw.height, layout);
  };

  return (
    <>
      <Line
        points={[0, 0, widthPx, 0, widthPx, heightPx, 0, heightPx]}
        closed
        stroke="#64748b"
        strokeWidth={2}
        listening={false}
      />
      {showHandles &&
        HANDLES.map((handle) => {
          const hx = handle.x(widthPx, heightPx);
          const hy = handle.y(widthPx, heightPx);
          return (
            <Rect
              key={handle.id}
              x={hx - HALF}
              y={hy - HALF}
              width={HANDLE}
              height={HANDLE}
              fill="#2563eb"
              stroke="#ffffff"
              strokeWidth={1}
              draggable
              onMouseEnter={(e) => {
                e.target.getStage()!.container().style.cursor = handle.cursor;
              }}
              onMouseLeave={(e) => {
                e.target.getStage()!.container().style.cursor = '';
              }}
              onMouseDown={(e) => {
                e.cancelBubble = true;
              }}
              onDragStart={(e) => {
                e.cancelBubble = true;
                e.target.getStage()!.container().style.cursor = handle.cursor;
              }}
              onDragMove={(e) => {
                e.cancelBubble = true;
                const next = applyPointer(handle.id, e.target);
                if (!next) return;
                // Keep the handle node parked on the live preview edge.
                const px = handle.x(next.width * SCALE, next.height * SCALE);
                const py = handle.y(next.width * SCALE, next.height * SCALE);
                e.target.position({ x: px - HALF, y: py - HALF });
                onPreview(next);
              }}
              onDragEnd={(e) => {
                e.cancelBubble = true;
                e.target.getStage()!.container().style.cursor = '';
                const next = applyPointer(handle.id, e.target);
                onPreview(null);
                if (!next) return;
                onCommit(next);
                const px = handle.x(next.width * SCALE, next.height * SCALE);
                const py = handle.y(next.width * SCALE, next.height * SCALE);
                e.target.position({ x: px - HALF, y: py - HALF });
              }}
            />
          );
        })}
    </>
  );
}
