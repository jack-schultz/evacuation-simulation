import { useMemo, useRef, useState } from 'react';
import { Layer, Line, Rect, Stage, Text, Circle, Group } from 'react-konva';
import type Konva from 'konva';
import type {
  BuildingLayout,
  EditorTool,
  OccupantFrameState,
  SelectedRef,
} from '../types/building';
import { SCALE, snap, uid } from '../utils';

interface Props {
  layout: BuildingLayout;
  tool: EditorTool;
  selected: SelectedRef;
  onSelect: (ref: SelectedRef) => void;
  onChange: (layout: BuildingLayout) => void;
  occupants?: OccupantFrameState[];
  congestedIds?: Set<string>;
  interactive?: boolean;
  /** Body radius in metres for playback dots (defaults to 0.25). */
  occupantRadiusM?: number;
}

const SPACE_COLORS: Record<string, string> = {
  room: '#dbeafe',
  corridor: '#e2e8f0',
  stairs: '#fde68a',
};

function findNearestSpaces(
  layout: BuildingLayout,
  x: number,
  y: number,
  count: number,
): string[] {
  return [...layout.spaces]
    .map((s) => {
      const cx = s.x + s.width / 2;
      const cy = s.y + s.height / 2;
      const d = (cx - x) ** 2 + (cy - y) ** 2;
      return { id: s.id, d };
    })
    .sort((a, b) => a.d - b.d)
    .slice(0, count)
    .map((s) => s.id);
}

function spaceContaining(layout: BuildingLayout, x: number, y: number): string | null {
  const hit = layout.spaces.find(
    (s) => x >= s.x && x <= s.x + s.width && y >= s.y && y <= s.y + s.height,
  );
  return hit?.id ?? null;
}

export function BuildingCanvas({
  layout,
  tool,
  selected,
  onSelect,
  onChange,
  occupants = [],
  congestedIds,
  interactive = true,
  occupantRadiusM = 0.25,
}: Props) {
  const [draft, setDraft] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const drawing = useRef(false);
  const start = useRef<{ x: number; y: number } | null>(null);
  const occupantRadiusPx = Math.max(occupantRadiusM * SCALE, 3);

  const widthPx = layout.width * SCALE;
  const heightPx = layout.height * SCALE;

  const gridLines = useMemo(() => {
    const lines: number[][] = [];
    for (let x = 0; x <= layout.width; x += 1) {
      lines.push([x * SCALE, 0, x * SCALE, heightPx]);
    }
    for (let y = 0; y <= layout.height; y += 1) {
      lines.push([0, y * SCALE, widthPx, y * SCALE]);
    }
    return lines;
  }, [layout.width, layout.height, widthPx, heightPx]);

  const toWorld = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    const stage = evt.target.getStage();
    const pos = stage?.getPointerPosition();
    if (!pos) return null;
    return { x: snap(pos.x / SCALE), y: snap(pos.y / SCALE) };
  };

  const onMouseDown = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    if (!interactive) return;
    if (tool === 'select') {
      if (evt.target === evt.target.getStage()) onSelect(null);
      return;
    }
    const p = toWorld(evt);
    if (!p) return;

    if (tool === 'door' || tool === 'exit' || tool === 'occupants') {
      // handled as click (mouseup with no drag)
      start.current = p;
      drawing.current = true;
      return;
    }

    drawing.current = true;
    start.current = p;
    setDraft({ x: p.x, y: p.y, w: 0, h: 0 });
  };

  const onMouseMove = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    if (!interactive || !drawing.current || !start.current) return;
    if (tool === 'door' || tool === 'exit' || tool === 'occupants') return;
    const p = toWorld(evt);
    if (!p) return;
    const x = Math.min(start.current.x, p.x);
    const y = Math.min(start.current.y, p.y);
    const w = Math.abs(p.x - start.current.x);
    const h = Math.abs(p.y - start.current.y);
    setDraft({ x, y, w, h });
  };

  const onMouseUp = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    if (!interactive || !drawing.current || !start.current) return;
    drawing.current = false;
    const p = toWorld(evt) ?? start.current;

    if (tool === 'door') {
      const nearest = findNearestSpaces(layout, p.x, p.y, 2);
      if (nearest.length < 2) {
        start.current = null;
        return;
      }
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
      start.current = null;
      return;
    }

    if (tool === 'exit') {
      const spaceId = spaceContaining(layout, p.x, p.y) ?? findNearestSpaces(layout, p.x, p.y, 1)[0];
      if (!spaceId) {
        start.current = null;
        return;
      }
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
      start.current = null;
      return;
    }

    if (tool === 'occupants') {
      const spaceId = spaceContaining(layout, p.x, p.y);
      if (!spaceId) {
        start.current = null;
        return;
      }
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
            walking_speed_mps: 1.2,
            destination_exit_id: null,
          },
        ],
      });
      onSelect({ kind: 'occupants', id });
      start.current = null;
      return;
    }

    const x = Math.min(start.current.x, p.x);
    const y = Math.min(start.current.y, p.y);
    const w = Math.max(snap(Math.abs(p.x - start.current.x)), 1);
    const h = Math.max(snap(Math.abs(p.y - start.current.y)), 1);
    setDraft(null);
    start.current = null;

    if (tool === 'wall') {
      const id = uid('wall');
      onChange({
        ...layout,
        walls: [...layout.walls, { id, name: 'Wall', x, y, width: w, height: h }],
      });
      onSelect({ kind: 'wall', id });
      return;
    }

    if (tool === 'room' || tool === 'corridor' || tool === 'stairs') {
      const id = uid(tool);
      onChange({
        ...layout,
        spaces: [
          ...layout.spaces,
          {
            id,
            name: `${tool} ${layout.spaces.length + 1}`,
            type: tool,
            x,
            y,
            width: w,
            height: h,
            capacity_density_per_m2: tool === 'corridor' ? 1.5 : null,
          },
        ],
      });
      onSelect({ kind: 'space', id });
    }
  };

  const isSelected = (kind: string, id: string) =>
    selected?.kind === kind && selected.id === id;

  return (
    <div className="canvas-wrap">
      <Stage
        width={widthPx}
        height={heightPx}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
      >
        <Layer>
          <Rect x={0} y={0} width={widthPx} height={heightPx} fill="#f8fafc" />
          {gridLines.map((pts, i) => (
            <Line key={i} points={pts} stroke="#e2e8f0" strokeWidth={1} listening={false} />
          ))}

          {layout.spaces.map((s) => (
            <Group
              key={s.id}
              onClick={() => interactive && onSelect({ kind: 'space', id: s.id })}
              draggable={interactive && tool === 'select'}
              x={s.x * SCALE}
              y={s.y * SCALE}
              onDragEnd={(e) => {
                const nx = snap(e.target.x() / SCALE);
                const ny = snap(e.target.y() / SCALE);
                e.target.position({ x: nx * SCALE, y: ny * SCALE });
                onChange({
                  ...layout,
                  spaces: layout.spaces.map((sp) =>
                    sp.id === s.id ? { ...sp, x: nx, y: ny } : sp,
                  ),
                });
              }}
            >
              <Rect
                width={s.width * SCALE}
                height={s.height * SCALE}
                fill={SPACE_COLORS[s.type]}
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
                width={s.width * SCALE}
                align="center"
                y={8}
                fontSize={12}
                fill="#334155"
                listening={false}
              />
            </Group>
          ))}

          {layout.walls.map((w) => (
            <Rect
              key={w.id}
              x={w.x * SCALE}
              y={w.y * SCALE}
              width={w.width * SCALE}
              height={w.height * SCALE}
              fill="#334155"
              opacity={0.85}
              stroke={isSelected('wall', w.id) ? '#2563eb' : undefined}
              strokeWidth={2}
              onClick={() => interactive && onSelect({ kind: 'wall', id: w.id })}
            />
          ))}

          {layout.flood?.enabled && (
            <Group listening={false}>
              <Circle x={layout.flood.x * SCALE} y={layout.flood.y * SCALE}
                radius={layout.flood.radius_m * SCALE}
                fill={`rgba(14, 165, 233, ${0.1 + layout.flood.intensity / 250})`}
                stroke={layout.flood.intensity >= 80 ? '#7c3aed' : '#0284c7'}
                strokeWidth={2} dash={[6, 4]} />
              <Text x={layout.flood.x * SCALE - 55} y={layout.flood.y * SCALE - 20}
                width={110} align="center" text={`Flood ${layout.flood.intensity}%`}
                fill="#075985" fontSize={12} />
              <Circle x={layout.flood.x * SCALE} y={layout.flood.y * SCALE}
                radius={3} fill="#075985" />
            </Group>
          )}

          {layout.doors.map((d) => (
            <Rect
              key={d.id}
              x={d.x * SCALE - 6}
              y={d.y * SCALE - 6}
              width={12}
              height={12}
              fill={congestedIds?.has(d.id) ? '#ef4444' : '#f59e0b'}
              stroke={isSelected('door', d.id) ? '#2563eb' : '#92400e'}
              strokeWidth={isSelected('door', d.id) ? 2 : 1}
              onClick={() => interactive && onSelect({ kind: 'door', id: d.id })}
            />
          ))}

          {layout.exits.map((ex) => (
            <Group key={ex.id} onClick={() => interactive && onSelect({ kind: 'exit', id: ex.id })}>
              <Rect
                x={ex.x * SCALE - 10}
                y={ex.y * SCALE - 10}
                width={20}
                height={20}
                fill={congestedIds?.has(ex.id) ? '#ef4444' : '#22c55e'}
                stroke={isSelected('exit', ex.id) ? '#2563eb' : '#166534'}
                strokeWidth={2}
              />
              <Text
                text="EXIT"
                x={ex.x * SCALE - 14}
                y={ex.y * SCALE + 12}
                fontSize={10}
                fill="#166534"
                listening={false}
              />
            </Group>
          ))}

          {layout.occupant_groups.map((g) => {
            const space = layout.spaces.find((s) => s.id === g.space_id);
            if (!space) return null;
            const cx = (space.x + space.width / 2) * SCALE;
            const cy = (space.y + space.height / 2) * SCALE;
            return (
              <Group
                key={g.id}
                onClick={() => interactive && onSelect({ kind: 'occupants', id: g.id })}
              >
                <Circle
                  x={cx}
                  y={cy}
                  radius={14}
                  fill={isSelected('occupants', g.id) ? '#7c3aed' : '#8b5cf6'}
                  opacity={occupants.length ? 0.25 : 0.9}
                />
                <Text
                  text={String(g.count)}
                  x={cx - 10}
                  y={cy - 5}
                  width={20}
                  align="center"
                  fontSize={11}
                  fill="#fff"
                  listening={false}
                />
              </Group>
            );
          })}

          {occupants
            .filter((o) => o.status !== 'evacuated')
            .map((o) => (
              <Circle
                key={o.id}
                x={o.x * SCALE}
                y={o.y * SCALE}
                radius={occupantRadiusPx}
                fill={o.status === 'trapped' ? '#7c3aed' : o.status === 'waiting' ? '#ef4444' : '#2563eb'}
                listening={false}
              />
            ))}

          {draft && (
            <Rect
              x={draft.x * SCALE}
              y={draft.y * SCALE}
              width={draft.w * SCALE}
              height={draft.h * SCALE}
              stroke="#2563eb"
              dash={[4, 4]}
              listening={false}
            />
          )}
        </Layer>
      </Stage>
    </div>
  );
}
