import type Konva from 'konva';
import type { BuildingLayout, EditorTool, SelectedRef } from '../../types/building';
import { SCALE, snap, uid, polygonBBox, samePoint, type Point } from '../../utils';
import { exitSpaceAt } from '../../exitPlacement';
import { findNearestSpaces, spaceContaining } from './geometryHelpers';

type DraftApi = {
  draftPoints: Point[];
  setDraftPoints: React.Dispatch<React.SetStateAction<Point[]>>;
  setCursor: (p: Point | null) => void;
  nearFirst: (p: Point) => boolean;
  commitSpace: (vertices: Point[]) => void;
  cancelDraft: () => void;
  SPACE_TOOLS: EditorTool[];
};

export function useCanvasInteraction({
  layout,
  tool,
  interactive,
  onSelect,
  onChange,
  draft,
}: {
  layout: BuildingLayout;
  tool: EditorTool;
  interactive: boolean;
  onSelect: (ref: SelectedRef) => void;
  onChange: (layout: BuildingLayout) => void;
  draft: DraftApi;
}) {
  const toWorld = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    const stage = evt.target.getStage();
    const pointer = stage?.getPointerPosition();
    if (!stage || !pointer) return null;
    const transform = stage.getAbsoluteTransform().copy().invert();
    const local = transform.point(pointer);
    return { x: snap(local.x / SCALE), y: snap(local.y / SCALE) };
  };

  const onMouseDown = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    if (!interactive) return;
    if (tool === 'select') {
      if (evt.target === evt.target.getStage()) onSelect(null);
      return;
    }
    if (evt.evt.button === 2 && draft.SPACE_TOOLS.includes(tool)) {
      evt.evt.preventDefault();
      draft.cancelDraft();
      return;
    }
    const p = toWorld(evt);
    if (!p) return;
    const point: Point = [p.x, p.y];

    if (draft.SPACE_TOOLS.includes(tool)) {
      if (draft.nearFirst(point)) {
        draft.commitSpace(draft.draftPoints);
        return;
      }
      draft.setDraftPoints((prev) => {
        if (prev.length > 0 && samePoint(prev[prev.length - 1], point)) return prev;
        return [...prev, point];
      });
      return;
    }

    if (tool === 'door') {
      const nearest = findNearestSpaces(layout, p.x, p.y, 2);
      if (nearest.length < 2) return;
      const id = uid('door');
      onChange({
        ...layout,
        doors: [
          ...layout.doors,
          {
            id,
            name: `Door ${layout.doors.length + 1}`,
            x: p.x,
            y: p.y,
            width: 0.9,
            connects: [nearest[0], nearest[1]],
            flow_rate_per_s: 0.8,
          },
        ],
      });
      onSelect({ kind: 'door', id });
      return;
    }

    if (tool === 'exit') {
      const spaceId = exitSpaceAt(layout, p.x, p.y);
      if (!spaceId) return;
      const id = uid('exit');
      onChange({
        ...layout,
        exits: [
          ...layout.exits,
          {
            id,
            name: `Exit ${layout.exits.length + 1}`,
            x: p.x,
            y: p.y,
            width: 1.2,
            connected_space_id: spaceId,
            flow_rate_per_s: 1.0,
          },
        ],
      });
      onSelect({ kind: 'exit', id });
      return;
    }

    if (tool === 'occupants' || tool === 'spawn') {
      const spaceId = spaceContaining(layout, p.x, p.y);
      if (!spaceId) return;
      const id = uid('group');
      onChange({
        ...layout,
        occupant_groups: [
          ...layout.occupant_groups,
          {
            id,
            name: `Group ${layout.occupant_groups.length + 1}`,
            count: 10,
            space_id: spaceId,
            spawn_x: p.x,
            spawn_y: p.y,
            walking_speed_mps: 1.2,
            destination_exit_id: null,
          },
        ],
      });
      onSelect({ kind: 'occupants', id });
    }
  };

  const onMouseMove = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    if (!interactive || !draft.SPACE_TOOLS.includes(tool)) return;
    const p = toWorld(evt);
    if (!p) return;
    draft.setCursor([p.x, p.y]);
  };

  const onContextMenu = (evt: Konva.KonvaEventObject<PointerEvent>) => {
    if (draft.SPACE_TOOLS.includes(tool) && draft.draftPoints.length > 0) {
      evt.evt.preventDefault();
      draft.cancelDraft();
    }
  };

  // All editable shapes use world coordinates at their drag anchor. Committing
  // through onChange keeps saving and the existing property controls in sync.
  const dragProps = (
    ref: SelectedRef,
    commit: (x: number, y: number) => void,
    width = 0,
    height = 0,
  ) => ({
    draggable: interactive && tool === 'select',
    onMouseEnter: (e: Konva.KonvaEventObject<MouseEvent>) => {
      if (interactive && tool === 'select') {
        e.target.getStage()!.container().style.cursor = 'grab';
      }
    },
    onMouseLeave: (e: Konva.KonvaEventObject<MouseEvent>) => {
      e.target.getStage()!.container().style.cursor = '';
    },
    onDragStart: (e: Konva.KonvaEventObject<DragEvent>) => {
      e.cancelBubble = true;
      onSelect(ref);
      e.target.getStage()!.container().style.cursor = 'grabbing';
    },
    onDragEnd: (e: Konva.KonvaEventObject<DragEvent>) => {
      e.cancelBubble = true;
      e.target.getStage()!.container().style.cursor = '';
      const x = Math.min(Math.max(0, layout.width - width), Math.max(0, snap(e.target.x() / SCALE)));
      const y = Math.min(Math.max(0, layout.height - height), Math.max(0, snap(e.target.y() / SCALE)));
      e.target.position({ x: x * SCALE, y: y * SCALE });
      commit(x, y);
    },
  });

  const resizeSpace = (
    space: BuildingLayout['spaces'][number],
    corner: 'nw' | 'ne' | 'sw' | 'se',
    localX: number,
    localY: number,
  ) => {
    const box = polygonBBox(space.vertices);
    if (box.width < 1e-9 || box.height < 1e-9) return;

    const pointerX = snap(box.x + localX / SCALE);
    const pointerY = snap(box.y + localY / SCALE);
    const right = box.x + box.width;
    const bottom = box.y + box.height;
    const minimumSize = 1;
    let nextX = box.x;
    let nextY = box.y;
    let nextWidth = box.width;
    let nextHeight = box.height;

    if (corner.includes('w')) {
      nextX = Math.min(Math.max(0, pointerX), right - minimumSize);
      nextWidth = right - nextX;
    } else {
      const nextRight = Math.min(Math.max(box.x + minimumSize, pointerX), layout.width);
      nextWidth = nextRight - box.x;
    }

    if (corner.includes('n')) {
      nextY = Math.min(Math.max(0, pointerY), bottom - minimumSize);
      nextHeight = bottom - nextY;
    } else {
      const nextBottom = Math.min(Math.max(box.y + minimumSize, pointerY), layout.height);
      nextHeight = nextBottom - box.y;
    }

    const scaleX = nextWidth / box.width;
    const scaleY = nextHeight / box.height;
    // Opposite corner stays fixed while the dragged corner moves.
    const anchorX = corner.includes('w') ? right : box.x;
    const anchorY = corner.includes('n') ? bottom : box.y;

    const vertices = space.vertices.map(
      ([vx, vy]) =>
        [
          snap(anchorX + (vx - anchorX) * scaleX),
          snap(anchorY + (vy - anchorY) * scaleY),
        ] as Point,
    );

    onChange({
      ...layout,
      spaces: layout.spaces.map((candidate) =>
        candidate.id === space.id ? { ...candidate, vertices } : candidate,
      ),
    });
  };

  return { onMouseDown, onMouseMove, onContextMenu, dragProps, resizeSpace };
}

export type DragPropsFn = ReturnType<typeof useCanvasInteraction>['dragProps'];
export type ResizeSpaceFn = ReturnType<typeof useCanvasInteraction>['resizeSpace'];
