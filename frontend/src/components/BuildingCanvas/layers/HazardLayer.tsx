import { Circle, Group, Text } from 'react-konva';
import type { BuildingLayout, EditorTool } from '../../../types/building';
import type { SmokeFloorState } from '../../../types/api';
import { SCALE } from '../../../utils';
import type { DragPropsFn } from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  tool: EditorTool;
  interactive: boolean;
  activeFloorId: string;
  showAllFloors?: boolean;
  floodRadiusM?: number | null;
  fireRadiusM?: number | null;
  smokeFloors?: SmokeFloorState[];
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
}

export function HazardLayer({
  layout,
  tool,
  interactive,
  activeFloorId,
  showAllFloors = false,
  floodRadiusM,
  fireRadiusM,
  smokeFloors = [],
  onChange,
  dragProps,
}: Props) {
  const onFloor = (floorId?: string | null) =>
    showAllFloors || (floorId ?? 'floor-0') === activeFloorId;

  const connectedSpaceIds = (x: number, y: number, floorId: string) => {
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
      .map((space) => (
      <Group
        key={`${space.id}-${x}-${y}-${radius}-${fill}`}
        clipFunc={(context) => {
          const vertices = space.vertices;
          if (vertices.length < 3) return;
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
    ));
  };

  const floodOnFloor = layout.flood?.enabled && onFloor(layout.flood.floor_id);
  const fireOnFloor = layout.fire?.enabled && onFloor(layout.fire.floor_id);
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

  return (
    <>
      {floodOnFloor && layout.flood && (
        clippedHazard(
          layout.flood.x,
          layout.flood.y,
          floodRadiusM ?? layout.flood.radius_m,
          `rgba(14, 165, 233, ${0.1 + layout.flood.intensity / 250})`,
          layout.flood.intensity >= 80 ? '#7c3aed' : '#0284c7',
          layout.flood.floor_id ?? 'floor-0',
        )
      )}
      {floodOnFloor && layout.flood && (
        <Group
          x={layout.flood.x * SCALE}
          y={layout.flood.y * SCALE}
          {...dragProps(null, (x, y) => {
            if (layout.flood) onChange({ ...layout, flood: { ...layout.flood, x, y } });
          })}
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
            stroke="#075985"
            strokeWidth={2}
            listening={interactive && tool === 'select'}
          />
          <Circle radius={3} fill="#075985" listening={false} />
        </Group>
      )}

      {fireOnFloor && layout.fire && (
        clippedHazard(
          layout.fire.x,
          layout.fire.y,
          fireRadiusM ?? layout.fire.radius_m,
          `rgba(249, 115, 22, ${0.1 + layout.fire.intensity / 250})`,
          layout.fire.intensity >= 80 ? '#b91c1c' : '#ea580c',
          layout.fire.floor_id ?? 'floor-0',
        )
      )}
      {fireOnFloor && layout.fire && (
        <Group
          x={layout.fire.x * SCALE}
          y={layout.fire.y * SCALE}
          {...dragProps(null, (x, y) => {
            if (layout.fire) onChange({ ...layout, fire: { ...layout.fire, x, y } });
          })}
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
            stroke="#9a3412"
            strokeWidth={2}
            listening={interactive && tool === 'select'}
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
