import { useRef } from 'react';
import type Konva from 'konva';
import type {
  BuildingLayout,
  EditorTool,
  ObjectRef,
  Selection,
} from '../../types/building';
import { applyContextSelect, isRefSelected, FIRE_REF_ID, FLOOD_REF_ID } from '../../types/editor';
import type { FireEmergency, FloodEmergency } from '../../types/building';
import { SCALE, snap, uid, polygonBBox, samePoint, type Point } from '../../utils';
import { exitSpaceAt } from '../../exitPlacement';
import { translateSelection } from '../../layout/clipboard';
import { findNearestSpaces, spaceContaining } from './geometryHelpers';
import { filterLayoutByFloor } from '../../layout/emptyLayout';

type DraftApi = {
  draftPoints: Point[];
  setDraftPoints: React.Dispatch<React.SetStateAction<Point[]>>;
  setCursor: (p: Point | null) => void;
  nearFirst: (p: Point) => boolean;
  commitSpace: (vertices: Point[]) => void;
  cancelDraft: () => void;
  SPACE_TOOLS: EditorTool[];
};

export type ContextMenuRequest = {
  clientX: number;
  clientY: number;
  worldX: number;
  worldY: number;
  target: 'object' | 'canvas';
  ref?: ObjectRef;
};

function defaultFlood(x: number, y: number, floorId: string): FloodEmergency {
  return {
    enabled: true,
    x,
    y,
    radius_m: 3,
    spread_speed_mps: 0.1,
    intensity: 50,
    floor_id: floorId,
  };
}

function defaultFire(x: number, y: number, floorId: string): FireEmergency {
  return {
    enabled: true,
    x,
    y,
    radius_m: 3,
    spread_speed_mps: 0.1,
    intensity: 50,
    floor_id: floorId,
    emit_smoke: true,
    smoke_visibility_m: 8,
    smoke_stair_spread_delay_s: 8,
    smoke_stair_intensity_factor: 0.85,
  };
}

export function useCanvasInteraction({
  layout,
  tool,
  interactive,
  selected,
  onSelect,
  onSelectObject,
  onChange,
  draft,
  onContextMenuRequest,
  activeFloorId,
}: {
  layout: BuildingLayout;
  tool: EditorTool;
  interactive: boolean;
  selected: Selection;
  onSelect: (selection: Selection) => void;
  onSelectObject: (
    ref: ObjectRef,
    modifiers: { shiftKey: boolean; metaKey: boolean; ctrlKey: boolean },
  ) => void;
  onChange: (layout: BuildingLayout) => void;
  draft: DraftApi;
  onContextMenuRequest?: (request: ContextMenuRequest) => void;
  activeFloorId: string;
}) {
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const floorLayout = filterLayoutByFloor(layout, activeFloorId);

  const dragOriginRef = useRef<{ x: number; y: number } | null>(null);
  const dragRefRef = useRef<ObjectRef | null>(null);
  const suppressNextClickRef = useRef(false);

  const toWorld = (evt: Konva.KonvaEventObject<MouseEvent | PointerEvent>) => {
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
      if (evt.target === evt.target.getStage()) onSelect([]);
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
      if (p.x < 0 || p.x > layout.width || p.y < 0 || p.y > layout.height) return;
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
      const nearest = findNearestSpaces(floorLayout, p.x, p.y, 2);
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
            floor_id: activeFloorId,
          },
        ],
      });
      onSelect([{ kind: 'door', id }]);
      return;
    }

    if (tool === 'exit') {
      const spaceId = exitSpaceAt(floorLayout, p.x, p.y);
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
            floor_id: activeFloorId,
          },
        ],
      });
      onSelect([{ kind: 'exit', id }]);
      return;
    }

    if (tool === 'occupants') {
      const spaceId = spaceContaining(floorLayout, p.x, p.y);
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
            floor_id: activeFloorId,
          },
        ],
      });
      onSelect([{ kind: 'occupants', id }]);
      return;
    }

    if (tool === 'flood' || tool === 'fire') {
      if (p.x < 0 || p.x > layout.width || p.y < 0 || p.y > layout.height) return;
      if (tool === 'flood') {
        const existing = layout.flood;
        const flood = existing
          ? { ...existing, x: p.x, y: p.y, floor_id: activeFloorId }
          : defaultFlood(p.x, p.y, activeFloorId);
        onChange({ ...layout, flood });
        onSelect([{ kind: 'flood', id: FLOOD_REF_ID }]);
      } else {
        const existing = layout.fire;
        const fire = existing
          ? { ...existing, x: p.x, y: p.y, floor_id: activeFloorId }
          : defaultFire(p.x, p.y, activeFloorId);
        onChange({ ...layout, fire });
        onSelect([{ kind: 'fire', id: FIRE_REF_ID }]);
      }
    }
  };

  const onMouseMove = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    if (!interactive || !draft.SPACE_TOOLS.includes(tool)) return;
    const p = toWorld(evt);
    if (!p) return;
    draft.setCursor([p.x, p.y]);
  };

  const onContextMenu = (evt: Konva.KonvaEventObject<PointerEvent>) => {
    evt.evt.preventDefault();

    if (draft.SPACE_TOOLS.includes(tool) && draft.draftPoints.length > 0) {
      draft.cancelDraft();
      return;
    }

    // Object layers handle their own context menus; only empty canvas here.
    if (evt.target !== evt.target.getStage()) return;
    if (!interactive || !onContextMenuRequest) return;

    const world = toWorld(evt);
    if (!world) return;

    onContextMenuRequest({
      clientX: evt.evt.clientX,
      clientY: evt.evt.clientY,
      worldX: world.x,
      worldY: world.y,
      target: 'canvas',
    });
  };

  // All editable shapes use world coordinates at their drag anchor. Committing
  // through onChange keeps saving and the existing property controls in sync.
  const dragProps = (
    ref: ObjectRef | null,
    commit: (x: number, y: number) => void,
    width = 0,
    height = 0,
    origin?: { x: number; y: number },
    options?: { validate?: (x: number, y: number) => boolean },
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
      if (ref) {
        const current = selectedRef.current;
        if (!isRefSelected(current, ref)) {
          onSelect([ref]);
          selectedRef.current = [ref];
        }
        dragRefRef.current = ref;
        dragOriginRef.current = origin ?? {
          x: snap(e.target.x() / SCALE),
          y: snap(e.target.y() / SCALE),
        };
      } else {
        dragRefRef.current = null;
        dragOriginRef.current = null;
      }
      e.target.getStage()!.container().style.cursor = 'grabbing';
    },
    onDragEnd: (e: Konva.KonvaEventObject<DragEvent>) => {
      e.cancelBubble = true;
      e.target.getStage()!.container().style.cursor = '';
      const x = Math.min(Math.max(0, layout.width - width), Math.max(0, snap(e.target.x() / SCALE)));
      const y = Math.min(Math.max(0, layout.height - height), Math.max(0, snap(e.target.y() / SCALE)));

      const dragRef = dragRefRef.current;
      const dragOrigin = dragOriginRef.current;
      const current = selectedRef.current;

      if (
        dragRef
        && dragOrigin
        && current.length > 1
        && isRefSelected(current, dragRef)
      ) {
        const dx = x - dragOrigin.x;
        const dy = y - dragOrigin.y;
        e.target.position({
          x: dragOrigin.x * SCALE,
          y: dragOrigin.y * SCALE,
        });
        onChange(translateSelection(layout, current, dx, dy));
        suppressNextClickRef.current = true;
        dragOriginRef.current = null;
        dragRefRef.current = null;
        return;
      }

      if (options?.validate && !options.validate(x, y)) {
        if (dragOrigin) {
          e.target.position({ x: dragOrigin.x * SCALE, y: dragOrigin.y * SCALE });
        }
        suppressNextClickRef.current = true;
        dragOriginRef.current = null;
        dragRefRef.current = null;
        return;
      }

      e.target.position({ x: x * SCALE, y: y * SCALE });
      commit(x, y);
      suppressNextClickRef.current = true;
      dragOriginRef.current = null;
      dragRefRef.current = null;
    },
  });

  const handleObjectClick = (
    ref: ObjectRef,
    evt: Konva.KonvaEventObject<MouseEvent>,
  ) => {
    if (!interactive) return;
    if (tool === 'obstacle') return;
    if (suppressNextClickRef.current) {
      suppressNextClickRef.current = false;
      return;
    }
    onSelectObject(ref, evt.evt);
  };

  const openObjectContextMenu = (
    ref: ObjectRef,
    evt: Konva.KonvaEventObject<PointerEvent>,
  ) => {
    evt.evt.preventDefault();
    evt.cancelBubble = true;

    if (draft.SPACE_TOOLS.includes(tool) && draft.draftPoints.length > 0) {
      draft.cancelDraft();
      return;
    }
    if (!interactive || !onContextMenuRequest) return;

    const next = applyContextSelect(selectedRef.current, ref);
    onSelect(next);
    selectedRef.current = next;

    const world = toWorld(evt);
    onContextMenuRequest({
      clientX: evt.evt.clientX,
      clientY: evt.evt.clientY,
      worldX: world?.x ?? 0,
      worldY: world?.y ?? 0,
      target: 'object',
      ref,
    });
  };

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

  return {
    onMouseDown,
    onMouseMove,
    onContextMenu,
    openObjectContextMenu,
    handleObjectClick,
    dragProps,
    resizeSpace,
    onSelectObject,
  };
}

export type DragPropsFn = ReturnType<typeof useCanvasInteraction>['dragProps'];
export type ResizeSpaceFn = ReturnType<typeof useCanvasInteraction>['resizeSpace'];
export type OpenObjectContextMenuFn = ReturnType<
  typeof useCanvasInteraction
>['openObjectContextMenu'];
export type HandleObjectClickFn = ReturnType<
  typeof useCanvasInteraction
>['handleObjectClick'];
