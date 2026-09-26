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
  return (
    <>
      {layout.flood?.enabled && (
        <Group
          x={layout.flood.x * SCALE}
          y={layout.flood.y * SCALE}
          {...dragProps(null, (x, y) => {
            if (layout.flood) onChange({ ...layout, flood: { ...layout.flood, x, y } });
          })}
        >
          <Circle
            radius={(floodRadiusM ?? layout.flood.radius_m) * SCALE}
            fill={`rgba(14, 165, 233, ${0.1 + layout.flood.intensity / 250})`}
            stroke={layout.flood.intensity >= 80 ? '#7c3aed' : '#0284c7'}
            strokeWidth={2}
            dash={[6, 4]}
            listening={false}
          />
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
        <Group
          x={layout.fire.x * SCALE}
          y={layout.fire.y * SCALE}
          {...dragProps(null, (x, y) => {
            if (layout.fire) onChange({ ...layout, fire: { ...layout.fire, x, y } });
          })}
        >
          <Circle
            radius={(fireRadiusM ?? layout.fire.radius_m) * SCALE}
            fill={`rgba(249, 115, 22, ${0.1 + layout.fire.intensity / 250})`}
            stroke={layout.fire.intensity >= 80 ? '#b91c1c' : '#ea580c'}
            strokeWidth={2}
            dash={[6, 4]}
            listening={false}
          />
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
