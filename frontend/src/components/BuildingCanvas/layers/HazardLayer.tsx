import { Circle, Group, Text } from 'react-konva';
import type {
  BuildingLayout,
  EditorTool,
  ObjectRef,
  Selection,
} from '../../../types/building';
import {
  FIRE_REF_ID,
  FLOOD_REF_ID,
  isRefSelected,
} from '../../../types/editor';
import type { FloodRoomState, SmokeFloorState } from '../../../types/api';
import { SCALE } from '../../../utils';
import type {
  DragPropsFn,
  HandleObjectClickFn,
  OpenObjectContextMenuFn,
} from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  tool: EditorTool;
  selected: Selection;
  interactive: boolean;
  activeFloorId: string;
  showAllFloors?: boolean;
  floodRadiusM?: number | null;
  floodRooms?: FloodRoomState[];
  fireRadiusM?: number | null;
  fireFloors?: SmokeFloorState[];
  smokeFloors?: SmokeFloorState[];
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
  onObjectClick: HandleObjectClickFn;
  onHover: (ref: ObjectRef | null) => void;
  onObjectContextMenu: OpenObjectContextMenuFn;
}

export function HazardLayer({
  layout,
  tool,
  selected,
  interactive,
  activeFloorId,
  showAllFloors = false,
  floodRadiusM,
  floodRooms = [],
  fireRadiusM,
  fireFloors = [],
  smokeFloors = [],
  onChange,
  dragProps,
  onObjectClick,
  onHover,
  onObjectContextMenu,
}: Props) {
  const onFloor = (floorId?: string | null) =>
    showAllFloors || (floorId ?? 'floor-0') === activeFloorId;

  const containsPoint = (vertices: [number, number][], x: number, y: number) => {
    let inside = false;
    for (let i = 0, j = vertices.length - 1; i < vertices.length; j = i, i += 1) {
      const [xi, yi] = vertices[i];
      const [xj, yj] = vertices[j];
      const cross = (x - xi) * (yj - yi) - (y - yi) * (xj - xi);
      const onSegment = Math.abs(cross) < 1e-8
        && x >= Math.min(xi, xj) - 1e-8 && x <= Math.max(xi, xj) + 1e-8
        && y >= Math.min(yi, yj) - 1e-8 && y <= Math.max(yi, yj) + 1e-8;
      if (onSegment) return true;
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
    return inside;
  };

  const connectedSpaceIds = (x: number, y: number, floorId: string) => {
    const floorSpaces = layout.spaces.filter(
      (space) => (space.floor_id ?? 'floor-0') === floorId,
    );
    const knownIds = new Set(floorSpaces.map((space) => space.id));
    const reachable = new Set(
      floorSpaces.filter((space) => containsPoint(space.vertices, x, y)).map((space) => space.id),
    );
    const queue = [...reachable];
    for (let index = 0; index < queue.length; index += 1) {
      const current = queue[index];
      for (const door of layout.doors) {
        if ((door.floor_id ?? 'floor-0') !== floorId) continue;
        const [a, b] = door.connects;
        const next = a === current ? b : b === current ? a : null;
        if (next && knownIds.has(next) && !reachable.has(next)) {
          reachable.add(next);
          queue.push(next);
        }
      }
    }
    return reachable;
  };

  const clipSpace = (
    spaceId: string,
    x: number,
    y: number,
    radius: number,
    fill: string,
    stroke: string,
    key: string,
  ) => {
    const space = layout.spaces.find((s) => s.id === spaceId);
    if (!space || space.vertices.length < 3) return null;
    return (
      <Group
        key={key}
        clipFunc={(context) => {
          const vertices = space.vertices;
          context.beginPath();
          context.moveTo(vertices[0][0] * SCALE, vertices[0][1] * SCALE);
          for (let i = 1; i < vertices.length; i += 1) {
            context.lineTo(vertices[i][0] * SCALE, vertices[i][1] * SCALE);
          }
          context.closePath();
        }}
        listening={false}
      >
        <Circle
          x={x * SCALE}
          y={y * SCALE}
          radius={radius * SCALE}
          fill={fill}
          stroke={stroke}
          strokeWidth={2}
          dash={[6, 4]}
          listening={false}
        />
      </Group>
    );
  };

  const clippedHazard = (
    x: number,
    y: number,
    radius: number,
    fill: string,
    stroke: string,
    floorId: string,
  ) => {
    const reachable = connectedSpaceIds(x, y, floorId);
    return layout.spaces
      .filter(
        (space) =>
          (space.floor_id ?? 'floor-0') === floorId && reachable.has(space.id),
      )
      .map((space) =>
        clipSpace(
          space.id,
          x,
          y,
          radius,
          fill,
          stroke,
          `${space.id}-${x}-${y}-${radius}-${fill}`,
        ),
      );
  };

  const floodEnabled = Boolean(layout.flood?.enabled);
  const floodOriginOnFloor = Boolean(layout.flood) && onFloor(layout.flood?.floor_id);
  const floodPlumesOnFloor = floodRooms.filter((plume) => {
    const space = layout.spaces.find((s) => s.id === plume.space_id);
    return space != null && onFloor(space.floor_id);
  });
  const fireExistsOnFloor = Boolean(layout.fire) && onFloor(layout.fire?.floor_id);
  const fireOnFloor = layout.fire?.enabled && fireExistsOnFloor;
  const fireOnActive = fireFloors.filter((p) => onFloor(p.floor_id));
  const smokeOnFloor = smokeFloors.filter((p) => onFloor(p.floor_id));
  // Before/without playback frames, preview smoke as a larger disc around the fire.
  const smokePreview =
    smokeOnFloor.length === 0
    && layout.fire?.enabled
    && layout.fire.emit_smoke !== false
    && onFloor(layout.fire.floor_id)
      ? {
          x: layout.fire.x,
          y: layout.fire.y,
          radius_m: layout.fire.radius_m * 1.4,
          intensity: Math.max(1, layout.fire.intensity * 0.8),
          floor_id: layout.fire.floor_id ?? 'floor-0',
        }
      : null;
  const firePreview =
    fireOnActive.length === 0 && fireOnFloor && layout.fire
      ? {
          x: layout.fire.x,
          y: layout.fire.y,
          radius_m: fireRadiusM ?? layout.fire.radius_m,
          intensity: layout.fire.intensity,
          floor_id: layout.fire.floor_id ?? 'floor-0',
        }
      : null;

  const floodFill = layout.flood
    ? `rgba(14, 165, 233, ${0.1 + layout.flood.intensity / 250})`
    : 'rgba(14, 165, 233, 0.2)';
  const floodStroke = layout.flood && layout.flood.intensity >= 80 ? '#7c3aed' : '#0284c7';

  const originFloodSpaceId =
    floodEnabled && floodOriginOnFloor && layout.flood
      ? layout.spaces.find(
          (space) =>
            (space.floor_id ?? 'floor-0') === (layout.flood?.floor_id ?? 'floor-0')
            && containsPoint(space.vertices, layout.flood!.x, layout.flood!.y),
        )?.id
      : undefined;

  const playbackFlood =
    floodPlumesOnFloor.length > 0
      ? floodPlumesOnFloor.map((plume) =>
          clipSpace(
            plume.space_id,
            plume.x,
            plume.y,
            plume.radius_m,
            floodFill,
            floodStroke,
            `flood-${plume.space_id}-${plume.x}-${plume.y}-${plume.radius_m}`,
          ),
        )
      : null;

  const floodRef: ObjectRef = { kind: 'flood', id: FLOOD_REF_ID };
  const fireRef: ObjectRef = { kind: 'fire', id: FIRE_REF_ID };
  const floodSelected = isRefSelected(selected, floodRef);
  const fireSelected = isRefSelected(selected, fireRef);
  const markerListening = interactive && tool === 'select';

  return (
    <>
      {floodEnabled && playbackFlood}
      {floodEnabled && floodOriginOnFloor && layout.flood && !playbackFlood && originFloodSpaceId && (
        clipSpace(
          originFloodSpaceId,
          layout.flood.x,
          layout.flood.y,
          floodRadiusM ?? layout.flood.radius_m,
          floodFill,
          floodStroke,
          `flood-preview-${originFloodSpaceId}`,
        )
      )}
      {floodOriginOnFloor && layout.flood && (
        <Group
          x={layout.flood.x * SCALE}
          y={layout.flood.y * SCALE}
          onClick={(e) => onObjectClick(floodRef, e)}
          onContextMenu={(e) => onObjectContextMenu(floodRef, e)}
          {...dragProps(floodRef, (x, y) => {
            if (layout.flood) onChange({ ...layout, flood: { ...layout.flood, x, y } });
          }, 0, 0, { x: layout.flood.x, y: layout.flood.y })}
          onMouseEnter={(event) => {
            onHover(floodRef);
            if (markerListening) event.target.getStage()!.container().style.cursor = 'grab';
          }}
          onMouseLeave={(event) => {
            onHover(null);
            event.target.getStage()!.container().style.cursor = '';
          }}
        >
          <Text
            x={-55}
            y={-30}
            width={110}
            align="center"
            text={`Flood ${layout.flood.intensity}%`}
            fill="#075985"
            fontSize={12}
            listening={false}
          />
          <Circle
            radius={10}
            fill="#e0f2fe"
            stroke={floodSelected ? '#2563eb' : '#075985'}
            strokeWidth={floodSelected ? 3 : 2}
            listening={markerListening}
          />
          <Circle radius={3} fill="#075985" listening={false} />
        </Group>
      )}

      {fireOnActive.map((plume) =>
        clippedHazard(
          plume.x,
          plume.y,
          plume.radius_m,
          `rgba(249, 115, 22, ${0.1 + plume.intensity / 250})`,
          plume.intensity >= 80 ? '#b91c1c' : '#ea580c',
          plume.floor_id,
        ),
      )}
      {firePreview && (
        clippedHazard(
          firePreview.x,
          firePreview.y,
          firePreview.radius_m,
          `rgba(249, 115, 22, ${0.1 + firePreview.intensity / 250})`,
          firePreview.intensity >= 80 ? '#b91c1c' : '#ea580c',
          firePreview.floor_id,
        )
      )}
      {fireExistsOnFloor && layout.fire && (
        <Group
          x={layout.fire.x * SCALE}
          y={layout.fire.y * SCALE}
          onClick={(e) => onObjectClick(fireRef, e)}
          onContextMenu={(e) => onObjectContextMenu(fireRef, e)}
          {...dragProps(fireRef, (x, y) => {
            if (layout.fire) onChange({ ...layout, fire: { ...layout.fire, x, y } });
          }, 0, 0, { x: layout.fire.x, y: layout.fire.y })}
          onMouseEnter={(event) => {
            onHover(fireRef);
            if (markerListening) event.target.getStage()!.container().style.cursor = 'grab';
          }}
          onMouseLeave={(event) => {
            onHover(null);
            event.target.getStage()!.container().style.cursor = '';
          }}
        >
          <Text
            x={-55}
            y={-30}
            width={110}
            align="center"
            text={`Fire ${layout.fire.intensity}%`}
            fill="#9a3412"
            fontSize={12}
            listening={false}
          />
          <Circle
            radius={10}
            fill="#ffedd5"
            stroke={fireSelected ? '#2563eb' : '#9a3412'}
            strokeWidth={fireSelected ? 3 : 2}
            listening={markerListening}
          />
          <Circle radius={3} fill="#9a3412" listening={false} />
        </Group>
      )}

      {smokeOnFloor.map((plume) =>
        clippedHazard(
          plume.x,
          plume.y,
          plume.radius_m,
          `rgba(100, 116, 139, ${0.12 + plume.intensity / 280})`,
          '#475569',
          plume.floor_id,
        ),
      )}
      {smokePreview && (
        clippedHazard(
          smokePreview.x,
          smokePreview.y,
          smokePreview.radius_m,
          `rgba(100, 116, 139, ${0.12 + smokePreview.intensity / 280})`,
          '#475569',
          smokePreview.floor_id,
        )
      )}
    </>
  );
}
