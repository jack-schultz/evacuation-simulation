import { useEffect, useMemo, useState } from 'react';
import { Layer, Line, Rect, Stage, Text, Circle, Group, Image as KonvaImage } from 'react-konva';
import type Konva from 'konva';
import type {
  BuildingLayout,
  EditorTool,
  OccupantFrameState,
  SelectedRef,
} from '../types/building';
import {
  SCALE,
  snap,
  uid,
  polygonArea,
  polygonBBox,
  polygonCentroid,
  pointInPolygon,
  samePoint,
  type Point,
} from '../utils';
import { exitSpaceAt, moveExit } from '../exitPlacement';

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
  floodRadiusM?: number | null;
  fireRadiusM?: number | null;
  floorPlanUrl?: string | null;
}

const SPACE_COLORS: Record<string, string> = {
  room: '#dbeafe',
  corridor: '#e2e8f0',
  stairs: '#fde68a',
};

const SPACE_TOOLS: EditorTool[] = ['room', 'corridor', 'stairs'];

function spaceCentroid(vertices: Point[]): Point {
  return polygonCentroid(vertices);
}

function findNearestSpaces(
  layout: BuildingLayout,
  x: number,
  y: number,
  count: number,
): string[] {
  return [...layout.spaces]
    .map((s) => {
      const [cx, cy] = spaceCentroid(s.vertices);
      const d = (cx - x) ** 2 + (cy - y) ** 2;
      return { id: s.id, d };
    })
    .sort((a, b) => a.d - b.d)
    .slice(0, count)
    .map((s) => s.id);
}

function spaceContaining(layout: BuildingLayout, x: number, y: number): string | null {
  const hit = layout.spaces.find((s) => pointInPolygon(x, y, s.vertices));
  return hit?.id ?? null;
}

function toFlatPoints(vertices: Point[]): number[] {
  return vertices.flatMap(([x, y]) => [x * SCALE, y * SCALE]);
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
  floodRadiusM,
  fireRadiusM,
  floorPlanUrl = null,
}: Props) {
  const [draftPoints, setDraftPoints] = useState<Point[]>([]);
  const [cursor, setCursor] = useState<Point | null>(null);
  const [floorPlanImage, setFloorPlanImage] = useState<HTMLImageElement | null>(null);
  const occupantRadiusPx = Math.max(occupantRadiusM * SCALE, 3);

  const widthPx = layout.width * SCALE;
  const heightPx = layout.height * SCALE;

  useEffect(() => {
    if (!floorPlanUrl) {
      setFloorPlanImage(null);
      return;
    }
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

  // Cancel in-progress polygon when tool changes or interaction is disabled.
  useEffect(() => {
    setDraftPoints([]);
    setCursor(null);
  }, [tool, interactive]);

  useEffect(() => {
    if (!interactive || !SPACE_TOOLS.includes(tool)) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDraftPoints([]);
        setCursor(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [tool, interactive]);

  const toWorld = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    const stage = evt.target.getStage();
    const pos = stage?.getPointerPosition();
    if (!pos) return null;
    return { x: snap(pos.x / SCALE), y: snap(pos.y / SCALE) };
  };

  const nearFirst = (p: Point) =>
    draftPoints.length >= 3 && samePoint(p, draftPoints[0]);

  const commitSpace = (vertices: Point[]) => {
    if (tool !== 'room' && tool !== 'corridor' && tool !== 'stairs') return;
    if (vertices.length < 3 || polygonArea(vertices) < 1e-6) return;
    const id = uid(tool);
    onChange({
      ...layout,
      spaces: [
        ...layout.spaces,
        {
          id,
          name: `${tool} ${layout.spaces.length + 1}`,
          type: tool,
          vertices,
          capacity_density_per_m2: tool === 'corridor' ? 1.5 : null,
        },
      ],
    });
    onSelect({ kind: 'space', id });
    setDraftPoints([]);
    setCursor(null);
  };

  const onMouseDown = (evt: Konva.KonvaEventObject<MouseEvent>) => {
    if (!interactive) return;
    if (tool === 'select') {
      if (evt.target === evt.target.getStage()) onSelect(null);
      return;
    }
    if (evt.evt.button === 2 && SPACE_TOOLS.includes(tool)) {
      evt.evt.preventDefault();
      setDraftPoints([]);
      setCursor(null);
      return;
    }
    const p = toWorld(evt);
    if (!p) return;
    const point: Point = [p.x, p.y];

    if (SPACE_TOOLS.includes(tool)) {
      if (nearFirst(point)) {
        commitSpace(draftPoints);
        return;
      }
      setDraftPoints((prev) => {
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
      const spaceId =
        exitSpaceAt(layout, p.x, p.y);
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
    if (!interactive || !SPACE_TOOLS.includes(tool)) return;
    const p = toWorld(evt);
    if (!p) return;
    setCursor([p.x, p.y]);
  };

  const onContextMenu = (evt: Konva.KonvaEventObject<PointerEvent>) => {
    if (SPACE_TOOLS.includes(tool) && draftPoints.length > 0) {
      evt.evt.preventDefault();
      setDraftPoints([]);
      setCursor(null);
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

  const closingPreview =
    draftPoints.length >= 3 && cursor && nearFirst(cursor);

  const draftLinePoints = useMemo(() => {
    if (draftPoints.length === 0) return null;
    const pts = [...draftPoints];
    if (cursor) {
      pts.push(closingPreview ? draftPoints[0] : cursor);
    }
    return toFlatPoints(pts);
  }, [draftPoints, cursor, closingPreview]);

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

  return (
    <div className="canvas-wrap">
      <Stage
        width={widthPx}
        height={heightPx}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onContextMenu={onContextMenu}
      >
        <Layer>
          <Rect x={0} y={0} width={widthPx} height={heightPx} fill="#f8fafc" listening={false} />
          {floorPlanImage && (
            <KonvaImage
              image={floorPlanImage}
              x={0}
              y={0}
              width={widthPx}
              height={heightPx}
              opacity={0.2}
              listening={false}
            />
          )}
          {gridLines.map((pts, i) => (
            <Line key={i} points={pts} stroke="#e2e8f0" strokeWidth={1} listening={false} />
          ))}

          {layout.spaces.map((s) => {
            const box = polygonBBox(s.vertices);
            const [cx, cy] = spaceCentroid(s.vertices);
            return (
              <Group
                key={s.id}
                x={box.x * SCALE}
                y={box.y * SCALE}
                onClick={() => interactive && onSelect({ kind: 'space', id: s.id })}
                {...dragProps(
                  { kind: 'space', id: s.id },
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
                )}
              >
                <Line
                  points={s.vertices.flatMap(([vx, vy]) => [
                    (vx - box.x) * SCALE,
                    (vy - box.y) * SCALE,
                  ])}
                  closed
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
                  x={(cx - box.x) * SCALE - 40}
                  y={(cy - box.y) * SCALE - 6}
                  width={80}
                  align="center"
                  fontSize={12}
                  fill="#334155"
                  listening={false}
                />
                {isSelected('space', s.id) && interactive && tool === 'select' &&
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
          })}

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
              <Circle radius={(fireRadiusM ?? layout.fire.radius_m) * SCALE}
                fill={`rgba(249, 115, 22, ${0.1 + layout.fire.intensity / 250})`}
                stroke={layout.fire.intensity >= 80 ? '#b91c1c' : '#ea580c'}
                strokeWidth={2} dash={[6, 4]} listening={false} />
              <Text x={-55} y={-30}
                width={110} align="center" text={`Fire ${layout.fire.intensity}%`}
                fill="#9a3412" fontSize={12} listening={false} />
              {/* Only the centre handle catches input, so the fire area does
                  not obstruct selecting or dragging the layout beneath it. */}
              <Circle radius={10} fill="#ffedd5" stroke="#9a3412" strokeWidth={2}
                listening={interactive && tool === 'select'} />
              <Circle radius={3} fill="#9a3412" listening={false} />
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
                  doors: layout.doors.map((door) =>
                    door.id === d.id ? { ...door, x, y } : door,
                  ),
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
            <Group
              key={ex.id}
              x={ex.x * SCALE}
              y={ex.y * SCALE}
              onClick={() => interactive && onSelect({ kind: 'exit', id: ex.id })}
              {...dragProps({ kind: 'exit', id: ex.id }, (x, y) => {
                onChange(moveExit(layout, ex.id, x, y));
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
              <Text text="EXIT" x={-14} y={12} fontSize={10} fill="#166534" listening={false} />
            </Group>
          ))}

          {layout.occupant_groups.map((g) => {
            const space = layout.spaces.find((s) => s.id === g.space_id);
            if (!space) return null;
            const [centerX, centerY] = spaceCentroid(space.vertices);
            const sx = g.spawn_x ?? centerX;
            const sy = g.spawn_y ?? centerY;
            const cx = sx * SCALE;
            const cy = sy * SCALE;
            return (
              <Group
                key={g.id}
                x={cx}
                y={cy}
                {...dragProps({ kind: 'occupants', id: g.id }, () => {})}
                onDragEnd={(e) => {
                  const x = snap(e.target.x() / SCALE);
                  const y = snap(e.target.y() / SCALE);
                  const spaceId = spaceContaining(
                    layout,
                    x,
                    y,
                  );
                  e.target.position({ x: cx, y: cy });
                  e.target.getStage()!.container().style.cursor = '';
                  e.cancelBubble = true;
                  if (spaceId) {
                    onChange({
                      ...layout,
                      occupant_groups: layout.occupant_groups.map((group) =>
                        group.id === g.id
                          ? { ...group, space_id: spaceId, spawn_x: x, spawn_y: y }
                          : group,
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
                fill={
                  o.status === 'trapped'
                    ? '#7c3aed'
                    : o.status === 'waiting'
                      ? '#ef4444'
                      : '#2563eb'
                }
                listening={false}
              />
            ))}

          {draftLinePoints && (
            <Line
              points={draftLinePoints}
              stroke={closingPreview ? '#16a34a' : '#2563eb'}
              strokeWidth={2}
              dash={[4, 4]}
              listening={false}
            />
          )}
          {draftPoints.map(([x, y], i) => (
            <Circle
              key={`draft-${i}`}
              x={x * SCALE}
              y={y * SCALE}
              radius={i === 0 && draftPoints.length >= 3 ? 6 : 3}
              fill={i === 0 && draftPoints.length >= 3 ? '#16a34a' : '#2563eb'}
              listening={false}
            />
          ))}
        </Layer>
      </Stage>
    </div>
  );
}
