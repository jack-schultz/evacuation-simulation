import { Group, Line, Rect, Text } from 'react-konva';
import type { BuildingLayout, EditorTool, SelectedRef } from '../../../types/building';
import { SCALE, snap, polygonBBox, type Point } from '../../../utils';
import { SPACE_COLORS, spaceCentroid } from '../geometryHelpers';
import type { DragPropsFn, ResizeSpaceFn } from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  tool: EditorTool;
  selected: SelectedRef;
  interactive: boolean;
  congestedIds?: Set<string>;
  floorPlanImage: HTMLImageElement | null;
  onSelect: (ref: SelectedRef) => void;
  onHover: (ref: SelectedRef) => void;
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
  resizeSpace: ResizeSpaceFn;
}

export function SpaceLayer({
  layout,
  tool,
  selected,
  interactive,
  congestedIds,
  floorPlanImage,
  onSelect,
  onHover,
  onChange,
  dragProps,
  resizeSpace,
}: Props) {
  const isSelected = (kind: string, id: string) =>
    selected?.kind === kind && selected.id === id;

  return (
    <>
      {layout.spaces.map((s) => {
        const box = polygonBBox(s.vertices);
        const [cx, cy] = spaceCentroid(s.vertices);
        return (
          <Group
            key={s.id}
            x={box.x * SCALE}
            y={box.y * SCALE}
            onClick={() => interactive && onSelect({ kind: 'space', id: s.id })}
            {...dragProps(
              { kind: 'space', id: s.id },
              (nx, ny) => {
                const dx = nx - box.x;
                const dy = ny - box.y;
                onChange({
                  ...layout,
                  spaces: layout.spaces.map((sp) =>
                    sp.id === s.id
                      ? {
                          ...sp,
                          vertices: sp.vertices.map(
                            ([vx, vy]) =>
                              [snap(vx + dx), snap(vy + dy)] as Point,
                          ),
                        }
                      : sp,
                  ),
                });
              },
              box.width,
              box.height,
            )}
            onMouseEnter={(event) => {
              onHover({ kind: 'space', id: s.id });
              if (interactive && tool === 'select') event.target.getStage()!.container().style.cursor = 'grab';
            }}
            onMouseLeave={(event) => {
              onHover(null);
              event.target.getStage()!.container().style.cursor = '';
            }}
          >
            <Line
              points={s.vertices.flatMap(([vx, vy]) => [
                (vx - box.x) * SCALE,
                (vy - box.y) * SCALE,
              ])}
              closed
              fill={SPACE_COLORS[s.type]}
              opacity={floorPlanImage ? 0.3 : 1}
              stroke={
                congestedIds?.has(s.id)
                  ? '#dc2626'
                  : isSelected('space', s.id)
                    ? '#2563eb'
                    : '#64748b'
              }
              strokeWidth={congestedIds?.has(s.id) || isSelected('space', s.id) ? 3 : 1}
            />
            <Text
              text={s.name}
              x={(cx - box.x) * SCALE - 40}
              y={(cy - box.y) * SCALE - 6}
              width={80}
              align="center"
              fontSize={12}
              fill="#334155"
              listening={false}
            />
            {isSelected('space', s.id) && interactive && tool === 'select' &&
              (['nw', 'ne', 'sw', 'se'] as const).map((corner) => {
                const handleX = corner.includes('w') ? 0 : box.width * SCALE;
                const handleY = corner.includes('n') ? 0 : box.height * SCALE;
                return (
                  <Rect
                    key={corner}
                    x={handleX - 5}
                    y={handleY - 5}
                    width={10}
                    height={10}
                    fill="#2563eb"
                    stroke="#ffffff"
                    strokeWidth={1}
                    draggable
                    onMouseDown={(e) => { e.cancelBubble = true; }}
                    onDragStart={(e) => { e.cancelBubble = true; }}
                    onDragEnd={(e) => {
                      e.cancelBubble = true;
                      resizeSpace(s, corner, e.target.x() + 5, e.target.y() + 5);
                      e.target.position({ x: handleX - 5, y: handleY - 5 });
                    }}
                  />
                );
              })}
          </Group>
        );
      })}
    </>
  );
}
