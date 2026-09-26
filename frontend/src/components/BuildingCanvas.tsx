import { useEffect, useMemo, useRef, useState } from 'react';
import { Layer, Line, Rect, Stage, Text, Circle, Group, Image as KonvaImage } from 'react-konva';
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
  floorPlanUrl?: string | null;
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
  floorPlanUrl = null,
}: Props) {
  const [draft, setDraft] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [floorPlanImage, setFloorPlanImage] = useState<HTMLImageElement | null>(null);
  const drawing = useRef(false);
  const start = useRef<{ x: number; y: number } | null>(null);
  const occupantRadiusPx = Math.max(occupantRadiusM * SCALE, 3);

  const widthPx = layout.width * SCALE;
  const heightPx = layout.height * SCALE;

  useEffect(() => {
    if (!floorPlanUrl) { setFloorPlanImage(null); return; }
    const image = new window.Image();
    image.onload = () => setFloorPlanImage(image);
    image.src = floorPlanUrl;
    return () => { image.onload = null; };
  }, [floorPlanUrl]);

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

    if (tool === 'door' || tool === 'exit' || tool === 'occupants' || tool === 'spawn') {
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
    if (tool === 'door' || tool === 'exit' || tool === 'occupants' || tool === 'spawn') return;
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

    if (tool === 'occupants' || tool === 'spawn') {
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
            spawn_x: p.x,
            spawn_y: p.y,
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
          <Rect x={0} y={0} width={widthPx} height={heightPx} fill="#f8fafc" listening={false} />
          {floorPlanImage && <KonvaImage image={floorPlanImage} x={0} y={0} width={widthPx} height={heightPx} opacity={0.2} listening={false} />}
          {gridLines.map((pts, i) => (
            <Line key={i} points={pts} stroke="#e2e8f0" strokeWidth={1} listening={false} />
          ))}

          {layout.spaces.map((s) => (
            <Group
              key={s.id}
              onClick={() => interactive && onSelect({ kind: 'space', id: s.id })}
              x={s.x * SCALE}
              y={s.y * SCALE}
              {...dragProps({ kind: 'space', id: s.id }, (x, y) => {
                onChange({
                  ...layout,
                  spaces: layout.spaces.map((sp) => sp.id === s.id ? { ...sp, x, y } : sp),
                });
              }, s.width, s.height)}
            >
              <Rect
                width={s.width * SCALE}
                height={s.height * SCALE}
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
                width={s.width * SCALE}
                align="center"
                y={8}
                fontSize={12}
                fill="#334155"
                listening={false}
              />
            </Group>
          ))}

          {layout.flood?.enabled && (
            <Group
              x={layout.flood.x * SCALE}
              y={layout.flood.y * SCALE}
              {...dragProps(null, (x, y) => {
                if (layout.flood) onChange({ ...layout, flood: { ...layout.flood, x, y } });
              })}
            >
              <Circle radius={layout.flood.radius_m * SCALE}
                fill={`rgba(14, 165, 233, ${0.1 + layout.flood.intensity / 250})`}
                stroke={layout.flood.intensity >= 80 ? '#7c3aed' : '#0284c7'}
                strokeWidth={2} dash={[6, 4]} listening={false} />
              <Text x={-55} y={-30}
                width={110} align="center" text={`Flood ${layout.flood.intensity}%`}
                fill="#075985" fontSize={12} listening={false} />
              {/* Only the centre handle catches input, so the flood area does
                  not obstruct selecting or dragging the layout beneath it. */}
              <Circle radius={10} fill="#e0f2fe" stroke="#075985" strokeWidth={2}
                listening={interactive && tool === 'select'} />
              <Circle radius={3} fill="#075985" listening={false} />
            </Group>
          )}

          {layout.doors.map((d) => (
            <Rect
              key={d.id}
              x={d.x * SCALE}
              y={d.y * SCALE}
              offsetX={6}
              offsetY={6}
              {...dragProps({ kind: 'door', id: d.id }, (x, y) => {
                onChange({
                  ...layout,
                  doors: layout.doors.map((door) => door.id === d.id ? { ...door, x, y } : door),
                });
              })}
              width={12}
              height={12}
              fill={congestedIds?.has(d.id) ? '#ef4444' : '#f59e0b'}
              stroke={isSelected('door', d.id) ? '#2563eb' : '#92400e'}
              strokeWidth={isSelected('door', d.id) ? 2 : 1}
              onClick={() => interactive && onSelect({ kind: 'door', id: d.id })}
            />
          ))}

          {layout.exits.map((ex) => (
            <Group key={ex.id}
              x={ex.x * SCALE} y={ex.y * SCALE}
              onClick={() => interactive && onSelect({ kind: 'exit', id: ex.id })}
              {...dragProps({ kind: 'exit', id: ex.id }, (x, y) => {
                onChange({
                  ...layout,
                  exits: layout.exits.map((exit) => exit.id === ex.id ? { ...exit, x, y } : exit),
                });
              })}
            >
              <Rect
                x={-10}
                y={-10}
                width={20}
                height={20}
                fill={congestedIds?.has(ex.id) ? '#ef4444' : '#22c55e'}
                stroke={isSelected('exit', ex.id) ? '#2563eb' : '#166534'}
                strokeWidth={2}
              />
              <Text
                text="EXIT"
                x={-14}
                y={12}
                fontSize={10}
                fill="#166534"
                listening={false}
              />
            </Group>
          ))}

          {layout.occupant_groups.map((g) => {
            const space = layout.spaces.find((s) => s.id === g.space_id);
            if (!space) return null;
            const spawnX = g.spawn_x ?? space.x + space.width / 2;
            const spawnY = g.spawn_y ?? space.y + space.height / 2;
            const cx = spawnX * SCALE;
            const cy = spawnY * SCALE;
            return (
              <Group
                key={g.id}
                x={cx}
                y={cy}
                {...dragProps({ kind: 'occupants', id: g.id }, () => {})}
                onDragEnd={(e) => {
                  const x = snap(e.target.x() / SCALE);
                  const y = snap(e.target.y() / SCALE);
                  const spaceId = spaceContaining(layout, x, y);
                  e.target.position({ x: cx, y: cy });
                  e.target.getStage()!.container().style.cursor = '';
                  e.cancelBubble = true;
                  if (spaceId) {
                    onChange({
                      ...layout,
                      occupant_groups: layout.occupant_groups.map((group) =>
                        group.id === g.id ? { ...group, space_id: spaceId, spawn_x: x, spawn_y: y } : group,
                      ),
                    });
                  }
                }}
                onClick={() => interactive && onSelect({ kind: 'occupants', id: g.id })}
              >
                <Circle
                  radius={14}
                  fill={isSelected('occupants', g.id) ? '#7c3aed' : '#8b5cf6'}
                  opacity={occupants.length ? 0.25 : 0.9}
                />
                <Text
                  text={String(g.count)}
                  x={-10}
                  y={-5}
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
