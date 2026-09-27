import { Group, Line, Rect, Text } from 'react-konva';
import type {
  BuildingLayout,
  EditorTool,
  ObjectRef,
  Selection,
} from '../../../types/building';
import { isRefSelected } from '../../../types/editor';
import { SCALE, snap, polygonBBox, type Point } from '../../../utils';
import {
  OVERLAP_FILL,
  SPACE_COLORS,
  findOverlappingSpaceIds,
  spaceCentroid,
} from '../geometryHelpers';
import type {
  DragPropsFn,
  HandleObjectClickFn,
  OpenObjectContextMenuFn,
  ResizeSpaceFn,
} from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  tool: EditorTool;
  selected: Selection;
  interactive: boolean;
  congestedIds?: Set<string>;
  floorPlanImage: HTMLImageElement | null;
  activeFloorId: string;
  showAllFloors?: boolean;
  onObjectClick: HandleObjectClickFn;
  onHover: (ref: ObjectRef | null) => void;
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
  resizeSpace: ResizeSpaceFn;
  onObjectContextMenu: OpenObjectContextMenuFn;
}

export function SpaceLayer({
  layout,
  tool,
  selected,
  interactive,
  congestedIds,
  floorPlanImage,
  activeFloorId,
  showAllFloors = false,
  onObjectClick,
  onHover,
  onChange,
  dragProps,
  resizeSpace,
  onObjectContextMenu,
}: Props) {
  const selectedSpace = (id: string) =>
    isRefSelected(selected, { kind: 'space', id });

  // Rooms (and corridors) behind stairs so nested stair openings stay visible.
  // During playback show every floor so the whole building moves at once;
  // inactive floors are drawn ghosted under the active plan.
  const floorSpaces = showAllFloors
    ? [...layout.spaces].sort((a, b) => {
        const aActive = (a.floor_id ?? 'floor-0') === activeFloorId ? 1 : 0;
        const bActive = (b.floor_id ?? 'floor-0') === activeFloorId ? 1 : 0;
        return aActive - bActive;
      })
    : layout.spaces.filter((s) => (s.floor_id ?? 'floor-0') === activeFloorId);
  const rooms = floorSpaces.filter((s) => s.type !== 'stairs');
  const stairs = floorSpaces.filter((s) => s.type === 'stairs');
  const overlappingIds = findOverlappingSpaceIds(layout);

  const renderSpace = (s: (typeof layout.spaces)[number]) => {
    const box = polygonBBox(s.vertices);
    const [cx, cy] = spaceCentroid(s.vertices);
    const active = selectedSpace(s.id);
    const overlapping = overlappingIds.has(s.id);
    const ref: ObjectRef = { kind: 'space', id: s.id };
    const onActiveFloor = (s.floor_id ?? 'floor-0') === activeFloorId;
    const ghost = showAllFloors && !onActiveFloor;
    return (
      <Group
        key={s.id}
        x={box.x * SCALE}
        y={box.y * SCALE}
        opacity={ghost ? 0.35 : 1}
        listening={!ghost && interactive}
        onClick={(e) => onObjectClick(ref, e)}
        onContextMenu={(e) => onObjectContextMenu(ref, e)}
        {...(ghost
          ? {}
          : dragProps(
          ref,
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
          { x: box.x, y: box.y },
        ))}
        onMouseEnter={(event) => {
          if (ghost) return;
          onHover(ref);
          if (interactive && tool === 'select') {
            event.target.getStage()!.container().style.cursor = 'grab';
          }
        }}
        onMouseLeave={(event) => {
          if (ghost) return;
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
          fill={overlapping ? OVERLAP_FILL : SPACE_COLORS[s.type]}
          opacity={floorPlanImage ? 0.3 : 1}
          stroke={
            overlapping || congestedIds?.has(s.id)
              ? '#dc2626'
              : active
                ? '#2563eb'
                : '#64748b'
          }
          strokeWidth={overlapping || congestedIds?.has(s.id) || active ? 3 : 1}
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
        {active && interactive && tool === 'select' && selected.length === 1 &&
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
  };

  return (
    <>
      {rooms.map(renderSpace)}
      {stairs.map(renderSpace)}
    </>
  );
}
