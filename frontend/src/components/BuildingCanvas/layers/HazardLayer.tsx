import { Circle, Group, Text } from 'react-konva';
import type {
  BuildingLayout,
  EditorTool,
  FireEmergency,
  FloodEmergency,
  ObjectRef,
  Selection,
} from '../../../types/building';
import { isRefSelected } from '../../../types/editor';
import type { FloodRoomState, SmokeFloorState, SmokeRoomState } from '../../../types/api';
import { layoutFires, layoutFloods } from '../../../layout/hazards';
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
  smokeRooms?: SmokeRoomState[];
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
  smokeRooms = [],
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
    keyPrefix: string,
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
          `${keyPrefix}-${space.id}-${x}-${y}-${radius}`,
        ),
      );
  };

  const floods = layoutFloods(layout);
  const fires = layoutFires(layout);
  const floodsOnFloor = floods.filter((f) => onFloor(f.floor_id));
  const firesOnFloor = fires.filter((f) => onFloor(f.floor_id));
  const floodPlumesOnFloor = floodRooms.filter((plume) => {
    const space = layout.spaces.find((s) => s.id === plume.space_id);
    return space != null && onFloor(space.floor_id);
  });
  const fireOnActive = fireFloors.filter((p) => onFloor(p.floor_id));
  const smokePlumesOnFloor = smokeRooms.filter((plume) => {
    const space = layout.spaces.find((s) => s.id === plume.space_id);
    return space != null && onFloor(space.floor_id);
  });
  const playbackSmoke = smokePlumesOnFloor.length > 0;
  const markerListening = interactive && tool === 'select';
  const playbackFlood = floodPlumesOnFloor.length > 0;

  const updateFlood = (id: string, patch: Partial<FloodEmergency>) => {
    onChange({
      ...layout,
      floods: layoutFloods(layout).map((f) => (f.id === id ? { ...f, ...patch } : f)),
      flood: undefined,
    });
  };

  const updateFire = (id: string, patch: Partial<FireEmergency>) => {
    onChange({
      ...layout,
      fires: layoutFires(layout).map((f) => (f.id === id ? { ...f, ...patch } : f)),
      fire: undefined,
    });
  };

  return (
    <>
      {playbackFlood
        && floodPlumesOnFloor.map((plume) =>
          clipSpace(
            plume.space_id,
            plume.x,
            plume.y,
            plume.radius_m,
            `rgba(14, 165, 233, ${0.1 + plume.intensity / 250})`,
            plume.intensity >= 80 ? '#7c3aed' : '#0284c7',
            `flood-${plume.space_id}-${plume.x}-${plume.y}-${plume.radius_m}`,
          ),
        )}

      {!playbackFlood
        && floodsOnFloor
          .filter((flood) => flood.enabled)
          .map((flood) => {
            const originSpaceId = layout.spaces.find(
              (space) =>
                (space.floor_id ?? 'floor-0') === (flood.floor_id ?? 'floor-0')
                && containsPoint(space.vertices, flood.x, flood.y),
            )?.id;
            if (!originSpaceId) return null;
            return clipSpace(
              originSpaceId,
              flood.x,
              flood.y,
              floodRadiusM ?? flood.radius_m,
              `rgba(14, 165, 233, ${0.1 + flood.intensity / 250})`,
              flood.intensity >= 80 ? '#7c3aed' : '#0284c7',
              `flood-preview-${flood.id}-${originSpaceId}`,
            );
          })}

      {floodsOnFloor.map((flood) => {
        const ref: ObjectRef = { kind: 'flood', id: flood.id };
        const active = isRefSelected(selected, ref);
        return (
          <Group
            key={`flood-marker-${flood.id}`}
            x={flood.x * SCALE}
            y={flood.y * SCALE}
            onClick={(e) => onObjectClick(ref, e)}
            onContextMenu={(e) => onObjectContextMenu(ref, e)}
            {...dragProps(ref, (x, y) => updateFlood(flood.id, { x, y }), 0, 0, {
              x: flood.x,
              y: flood.y,
            })}
            onMouseEnter={(event) => {
              onHover(ref);
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
              text={`Flood ${flood.intensity}%`}
              fill="#075985"
              fontSize={12}
              listening={false}
            />
            <Circle
              radius={10}
              fill="#e0f2fe"
              stroke={active ? '#2563eb' : '#075985'}
              strokeWidth={active ? 3 : 2}
              listening={markerListening}
            />
            <Circle radius={3} fill="#075985" listening={false} />
          </Group>
        );
      })}

      {fireOnActive.map((plume, index) =>
        clippedHazard(
          plume.x,
          plume.y,
          plume.radius_m,
          `rgba(249, 115, 22, ${0.1 + plume.intensity / 250})`,
          plume.intensity >= 80 ? '#b91c1c' : '#ea580c',
          plume.floor_id,
          `fire-play-${index}`,
        ),
      )}
      {fireOnActive.length === 0
        && firesOnFloor
          .filter((fire) => fire.enabled)
          .map((fire) =>
            clippedHazard(
              fire.x,
              fire.y,
              fireRadiusM ?? fire.radius_m,
              `rgba(249, 115, 22, ${0.1 + fire.intensity / 250})`,
              fire.intensity >= 80 ? '#b91c1c' : '#ea580c',
              fire.floor_id ?? 'floor-0',
              `fire-preview-${fire.id}`,
            ),
          )}

      {firesOnFloor.map((fire) => {
        const ref: ObjectRef = { kind: 'fire', id: fire.id };
        const active = isRefSelected(selected, ref);
        return (
          <Group
            key={`fire-marker-${fire.id}`}
            x={fire.x * SCALE}
            y={fire.y * SCALE}
            onClick={(e) => onObjectClick(ref, e)}
            onContextMenu={(e) => onObjectContextMenu(ref, e)}
            {...dragProps(ref, (x, y) => updateFire(fire.id, { x, y }), 0, 0, {
              x: fire.x,
              y: fire.y,
            })}
            onMouseEnter={(event) => {
              onHover(ref);
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
              text={`Fire ${fire.intensity}%`}
              fill="#9a3412"
              fontSize={12}
              listening={false}
            />
            <Circle
              radius={10}
              fill="#ffedd5"
              stroke={active ? '#2563eb' : '#9a3412'}
              strokeWidth={active ? 3 : 2}
              listening={markerListening}
            />
            <Circle radius={3} fill="#9a3412" listening={false} />
          </Group>
        );
      })}

      {playbackSmoke
        && smokePlumesOnFloor.map((plume) =>
          clipSpace(
            plume.space_id,
            plume.x,
            plume.y,
            plume.radius_m,
            `rgba(100, 116, 139, ${0.12 + plume.intensity / 280})`,
            '#475569',
            `smoke-${plume.space_id}-${plume.x}-${plume.y}-${plume.radius_m}`,
          ),
        )}
      {!playbackSmoke
        && firesOnFloor
          .filter((fire) => fire.enabled && fire.emit_smoke !== false)
          .map((fire) => {
            const originSpaceId = layout.spaces.find(
              (space) =>
                (space.floor_id ?? 'floor-0') === (fire.floor_id ?? 'floor-0')
                && containsPoint(space.vertices, fire.x, fire.y),
            )?.id;
            if (!originSpaceId) return null;
            return clipSpace(
              originSpaceId,
              fire.x,
              fire.y,
              fire.radius_m * 1.4,
              `rgba(100, 116, 139, ${0.12 + Math.max(1, fire.intensity * 0.8) / 280})`,
              '#475569',
              `smoke-preview-${fire.id}-${originSpaceId}`,
            );
          })}
    </>
  );
}
