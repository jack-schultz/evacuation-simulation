import { Circle, Group, Text } from 'react-konva';
import type { BuildingLayout, EditorTool } from '../../../types/building';
import { SCALE } from '../../../utils';
import type { DragPropsFn } from '../useCanvasInteraction';

interface Props {
  layout: BuildingLayout;
  tool: EditorTool;
  interactive: boolean;
  floodRadiusM?: number | null;
  fireRadiusM?: number | null;
  onChange: (layout: BuildingLayout) => void;
  dragProps: DragPropsFn;
}

export function HazardLayer({
  layout,
  tool,
  interactive,
  floodRadiusM,
  fireRadiusM,
  onChange,
  dragProps,
}: Props) {
  const connectedSpaceIds = (x: number, y: number) => {
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

    const knownIds = new Set(layout.spaces.map((space) => space.id));
    const reachable = new Set(
      layout.spaces.filter((space) => containsPoint(space.vertices, x, y)).map((space) => space.id),
    );
    const queue = [...reachable];
    for (let index = 0; index < queue.length; index += 1) {
      const current = queue[index];
      for (const door of layout.doors) {
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
  ) => {
    const reachable = connectedSpaceIds(x, y);
    return layout.spaces.filter((space) => reachable.has(space.id)).map((space) => (
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

  return (
    <>
      {layout.flood?.enabled && (
        clippedHazard(
          layout.flood.x,
          layout.flood.y,
          floodRadiusM ?? layout.flood.radius_m,
          `rgba(14, 165, 233, ${0.1 + layout.flood.intensity / 250})`,
          layout.flood.intensity >= 80 ? '#7c3aed' : '#0284c7',
        )
      )}
      {layout.flood?.enabled && (
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

      {layout.fire?.enabled && (
        clippedHazard(
          layout.fire.x,
          layout.fire.y,
          fireRadiusM ?? layout.fire.radius_m,
          `rgba(249, 115, 22, ${0.1 + layout.fire.intensity / 250})`,
          layout.fire.intensity >= 80 ? '#b91c1c' : '#ea580c',
        )
      )}
      {layout.fire?.enabled && (
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
          {/* Only the centre handle catches input, so the fire area does
              not obstruct selecting or dragging the layout beneath it. */}
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
    </>
  );
}
