import { useEffect, useMemo, useState } from 'react';
import { Circle, Layer, Line, Rect, Stage, Image as KonvaImage } from 'react-konva';
import type {
  BuildingLayout,
  EditorTool,
  OccupantFrameState,
  OccupantResult,
  SelectedRef,
} from '../../types/building';
import { SCALE } from '../../utils';
import { usePolygonDraft } from './usePolygonDraft';
import { useCanvasInteraction } from './useCanvasInteraction';
import { useCanvasViewport } from './useCanvasViewport';
import { SpaceLayer } from './layers/SpaceLayer';
import { HazardLayer } from './layers/HazardLayer';
import { OpeningsLayer } from './layers/OpeningsLayer';
import { PathsLayer } from './layers/PathsLayer';
import { OccupantsLayer } from './layers/OccupantsLayer';

interface Props {
  layout: BuildingLayout;
  tool: EditorTool;
  selected: SelectedRef;
  onSelect: (ref: SelectedRef) => void;
  onChange: (layout: BuildingLayout) => void;
  occupants?: OccupantFrameState[];
  routeOccupants?: OccupantResult[];
  showPaths?: boolean;
  congestedIds?: Set<string>;
  interactive?: boolean;
  /** Body radius in metres for playback dots (defaults to 0.25). */
  occupantRadiusM?: number;
  floodRadiusM?: number | null;
  fireRadiusM?: number | null;
  floorPlanUrl?: string | null;
}

export function BuildingCanvas({
  layout,
  tool,
  selected,
  onSelect,
  onChange,
  occupants = [],
  routeOccupants = [],
  showPaths = false,
  congestedIds,
  interactive = true,
  occupantRadiusM = 0.25,
  floodRadiusM,
  fireRadiusM,
  floorPlanUrl = null,
}: Props) {
  const [floorPlanImage, setFloorPlanImage] = useState<HTMLImageElement | null>(null);
  const occupantRadiusPx = Math.max(occupantRadiusM * SCALE, 3);

  const widthPx = layout.width * SCALE;
  const heightPx = layout.height * SCALE;

  const {
    containerRef,
    size,
    viewport,
    onWheel,
    beginPan,
    onPanMove,
    endPan,
    isPanning,
    zoomBy,
    resetView,
  } = useCanvasViewport(widthPx, heightPx);

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

  const draft = usePolygonDraft({
    tool,
    interactive,
    layout,
    onChange,
    onSelect,
  });

  const { onMouseDown, onMouseMove, onContextMenu, dragProps, resizeSpace } =
    useCanvasInteraction({
      layout,
      tool,
      interactive,
      onSelect,
      onChange,
      draft,
    });

  return (
    <div className="canvas-wrap" ref={containerRef}>
      <div className="canvas-zoom-controls" role="group" aria-label="Canvas zoom">
        <button type="button" title="Zoom in" aria-label="Zoom in" onClick={() => zoomBy(ZOOM_STEP)}>
          +
        </button>
        <button type="button" title="Zoom out" aria-label="Zoom out" onClick={() => zoomBy(1 / ZOOM_STEP)}>
          −
        </button>
        <button type="button" title="Reset view" aria-label="Reset view" onClick={resetView}>
          {Math.round(viewport.scale * 100)}%
        </button>
      </div>
      <Stage
        width={size.width}
        height={size.height}
        scaleX={viewport.scale}
        scaleY={viewport.scale}
        x={viewport.x}
        y={viewport.y}
        onWheel={onWheel}
        onMouseDown={(evt) => {
          if (beginPan(evt, { allowEmpty: tool === 'select' || !interactive })) return;
          onMouseDown(evt);
        }}
        onMouseMove={(evt) => {
          if (isPanning()) {
            onPanMove(evt);
            return;
          }
          onMouseMove(evt);
        }}
        onMouseUp={(evt) => {
          if (!isPanning()) return;
          const moved = endPan(evt);
          if (!moved && evt.target === evt.target.getStage() && tool === 'select') {
            onSelect(null);
          }
        }}
        onMouseLeave={() => {
          if (isPanning()) endPan();
        }}
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

          <SpaceLayer
            layout={layout}
            tool={tool}
            selected={selected}
            interactive={interactive}
            congestedIds={congestedIds}
            floorPlanImage={floorPlanImage}
            onSelect={onSelect}
            onChange={onChange}
            dragProps={dragProps}
            resizeSpace={resizeSpace}
          />

          <HazardLayer
            layout={layout}
            tool={tool}
            interactive={interactive}
            floodRadiusM={floodRadiusM}
            fireRadiusM={fireRadiusM}
            onChange={onChange}
            dragProps={dragProps}
          />

          <OpeningsLayer
            layout={layout}
            selected={selected}
            interactive={interactive}
            congestedIds={congestedIds}
            onSelect={onSelect}
            onChange={onChange}
            dragProps={dragProps}
          />

          {showPaths && <PathsLayer occupants={routeOccupants} />}

          <OccupantsLayer
            layout={layout}
            selected={selected}
            interactive={interactive}
            occupants={occupants}
            occupantRadiusPx={occupantRadiusPx}
            onSelect={onSelect}
            onChange={onChange}
            dragProps={dragProps}
          />

          {draft.draftLinePoints && (
            <Line
              points={draft.draftLinePoints}
              stroke={draft.closingPreview ? '#16a34a' : '#2563eb'}
              strokeWidth={2}
              dash={[4, 4]}
              listening={false}
            />
          )}
          {draft.draftPoints.map(([x, y], i) => (
            <Circle
              key={`draft-${i}`}
              x={x * SCALE}
              y={y * SCALE}
              radius={i === 0 && draft.draftPoints.length >= 3 ? 6 : 3}
              fill={i === 0 && draft.draftPoints.length >= 3 ? '#16a34a' : '#2563eb'}
              listening={false}
            />
          ))}
        </Layer>
      </Stage>
    </div>
  );
}

const ZOOM_STEP = 1.15;
