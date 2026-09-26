import { useCallback, useEffect, useMemo, useState } from 'react';
import { Circle, Layer, Line, Rect, Stage, Image as KonvaImage } from 'react-konva';
import type {
  BuildingLayout,
  EditorTool,
  ObjectRef,
  OccupantFrameState,
  OccupantResult,
  Selection,
} from '../../types/building';
import { SCALE } from '../../utils';
import { ContextMenu, type ContextMenuState } from '../ContextMenu';
import { usePolygonDraft } from './usePolygonDraft';
import { useCanvasInteraction } from './useCanvasInteraction';
import { useCanvasViewport } from './useCanvasViewport';
import { BuildingBoundsLayer } from './layers/BuildingBoundsLayer';
import { SpaceLayer } from './layers/SpaceLayer';
import { HazardLayer } from './layers/HazardLayer';
import { OpeningsLayer } from './layers/OpeningsLayer';
import { PathsLayer } from './layers/PathsLayer';
import { OccupantsLayer } from './layers/OccupantsLayer';

interface Props {
  layout: BuildingLayout;
  tool: EditorTool;
  selected: Selection;
  onSelect: (selection: Selection) => void;
  onSelectObject: (
    ref: ObjectRef,
    modifiers: { shiftKey: boolean; metaKey: boolean; ctrlKey: boolean },
  ) => void;
  onChange: (layout: BuildingLayout) => void;
  onCopy: () => void;
  onCut: () => void;
  onPaste: (worldPoint?: { x: number; y: number }) => void;
  onDuplicate: () => void;
  onDeleteSelected: () => void;
  canPaste: boolean;
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
  onSelectObject,
  onChange,
  onCopy,
  onCut,
  onPaste,
  onDuplicate,
  onDeleteSelected,
  canPaste,
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
  const [hoveredObject, setHoveredObject] = useState<ObjectRef | null>(null);
  const [previewSize, setPreviewSize] = useState<{ width: number; height: number } | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const occupantRadiusPx = Math.max(occupantRadiusM * SCALE, 3);

  const displayWidth = previewSize?.width ?? layout.width;
  const displayHeight = previewSize?.height ?? layout.height;
  const widthPx = displayWidth * SCALE;
  const heightPx = displayHeight * SCALE;

  // Viewport fits committed layout only so drag-preview does not refit every move.
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
  } = useCanvasViewport(layout.width * SCALE, layout.height * SCALE);

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

  useEffect(() => {
    setPreviewSize(null);
  }, [layout.width, layout.height]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.key.toLowerCase() !== 'e'
        || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey
        || !interactive || !hoveredObject
      ) return;
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('input, textarea, select, button, [contenteditable]')) return;
      event.preventDefault();
      onSelect([hoveredObject]);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [hoveredObject, interactive, onSelect]);

  const gridLines = useMemo(() => {
    const lines: number[][] = [];
    for (let x = 0; x <= displayWidth; x += 1) {
      lines.push([x * SCALE, 0, x * SCALE, heightPx]);
    }
    for (let y = 0; y <= displayHeight; y += 1) {
      lines.push([0, y * SCALE, widthPx, y * SCALE]);
    }
    return lines;
  }, [displayWidth, displayHeight, widthPx, heightPx]);

  const draft = usePolygonDraft({
    tool,
    interactive,
    layout,
    onChange,
    onSelect,
  });

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  const { onMouseDown, onMouseMove, onContextMenu, openObjectContextMenu, handleObjectClick, dragProps, resizeSpace } =
    useCanvasInteraction({
      layout,
      tool,
      interactive,
      selected,
      onSelect,
      onSelectObject,
      onChange,
      draft,
      onContextMenuRequest: (request) => {
        setContextMenu({
          x: request.clientX,
          y: request.clientY,
          worldX: request.worldX,
          worldY: request.worldY,
          target: request.target,
        });
      },
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
            onSelect([]);
          }
        }}
        onMouseLeave={() => {
          if (isPanning()) endPan();
          setHoveredObject(null);
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
            onObjectClick={handleObjectClick}
            onHover={setHoveredObject}
            onChange={onChange}
            dragProps={dragProps}
            resizeSpace={resizeSpace}
            onObjectContextMenu={openObjectContextMenu}
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
            onObjectClick={handleObjectClick}
            onHover={setHoveredObject}
            onChange={onChange}
            dragProps={dragProps}
            onObjectContextMenu={openObjectContextMenu}
          />

          {showPaths && <PathsLayer occupants={routeOccupants} />}

          <OccupantsLayer
            layout={layout}
            selected={selected}
            interactive={interactive}
            occupants={occupants}
            occupantRadiusPx={occupantRadiusPx}
            onObjectClick={handleObjectClick}
            onHover={setHoveredObject}
            onChange={onChange}
            dragProps={dragProps}
            onObjectContextMenu={openObjectContextMenu}
          />

          <BuildingBoundsLayer
            layout={layout}
            widthM={displayWidth}
            heightM={displayHeight}
            tool={tool}
            interactive={interactive}
            onPreview={setPreviewSize}
            onCommit={(next) => {
              setPreviewSize(null);
              if (next.width === layout.width && next.height === layout.height) return;
              onChange({ ...layout, width: next.width, height: next.height });
            }}
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

      <ContextMenu
        state={contextMenu}
        onClose={closeContextMenu}
        canPaste={canPaste}
        hasSelection={selected.length > 0}
        onDuplicate={onDuplicate}
        onCopy={onCopy}
        onCut={onCut}
        onPaste={() => {
          if (contextMenu?.worldX != null && contextMenu.worldY != null) {
            onPaste({ x: contextMenu.worldX, y: contextMenu.worldY });
          } else {
            onPaste();
          }
        }}
        onDelete={onDeleteSelected}
      />
    </div>
  );
}

const ZOOM_STEP = 1.15;
