import { useCallback, useEffect, useRef, useState } from 'react';
import type { KonvaEventObject } from 'konva/lib/Node';

const MIN_SCALE = 0.25;
const MAX_SCALE = 4;
const ZOOM_FACTOR = 1.08;

export type Viewport = {
  scale: number;
  x: number;
  y: number;
};

function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}

function fitViewport(
  contentWidth: number,
  contentHeight: number,
  viewWidth: number,
  viewHeight: number,
): Viewport {
  const padding = 48;
  const fit = Math.min(
    (viewWidth - padding) / contentWidth,
    (viewHeight - padding) / contentHeight,
    1,
  );
  const scale = clampScale(Number.isFinite(fit) ? fit : 1);
  return {
    scale,
    x: (viewWidth - contentWidth * scale) / 2,
    y: (viewHeight - contentHeight * scale) / 2,
  };
}

export function useCanvasViewport(contentWidth: number, contentHeight: number) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  const [viewport, setViewport] = useState<Viewport>({ scale: 1, x: 0, y: 0 });
  const panning = useRef<{ lastX: number; lastY: number; moved: boolean } | null>(null);
  const spaceDown = useRef(false);
  const fittedFor = useRef<{ w: number; h: number } | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const sync = () => {
      const next = { width: Math.max(1, el.clientWidth), height: Math.max(1, el.clientHeight) };
      setSize((prev) =>
        prev.width === next.width && prev.height === next.height ? prev : next,
      );
    };
    sync();
    const observer = new ResizeObserver(sync);
    observer.observe(el);
    const blockMiddleAutoscroll = (event: MouseEvent) => {
      if (event.button === 1) event.preventDefault();
    };
    el.addEventListener('mousedown', blockMiddleAutoscroll);
    el.addEventListener('auxclick', blockMiddleAutoscroll);
    return () => {
      observer.disconnect();
      el.removeEventListener('mousedown', blockMiddleAutoscroll);
      el.removeEventListener('auxclick', blockMiddleAutoscroll);
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.code !== 'Space' || event.repeat) return;
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      spaceDown.current = true;
      event.preventDefault();
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === 'Space') spaceDown.current = false;
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, []);

  useEffect(() => {
    if (size.width <= 0 || size.height <= 0 || contentWidth <= 0 || contentHeight <= 0) return;
    const prev = fittedFor.current;
    if (prev && prev.w === contentWidth && prev.h === contentHeight) return;
    fittedFor.current = { w: contentWidth, h: contentHeight };
    setViewport(fitViewport(contentWidth, contentHeight, size.width, size.height));
  }, [contentWidth, contentHeight, size.height, size.width]);

  const onWheel = useCallback((evt: KonvaEventObject<WheelEvent>) => {
    evt.evt.preventDefault();
    const stage = evt.target.getStage();
    const pointer = stage?.getPointerPosition();
    if (!pointer) return;

    // Pinch / ctrl-wheel zooms; otherwise scroll pans the view.
    if (evt.evt.ctrlKey || evt.evt.metaKey) {
      const direction = evt.evt.deltaY > 0 ? 1 / ZOOM_FACTOR : ZOOM_FACTOR;
      setViewport((current) => {
        const scale = clampScale(current.scale * direction);
        if (scale === current.scale) return current;
        const worldX = (pointer.x - current.x) / current.scale;
        const worldY = (pointer.y - current.y) / current.scale;
        return {
          scale,
          x: pointer.x - worldX * scale,
          y: pointer.y - worldY * scale,
        };
      });
      return;
    }

    setViewport((current) => ({
      ...current,
      x: current.x - evt.evt.deltaX,
      y: current.y - evt.evt.deltaY,
    }));
  }, []);

  const beginPan = useCallback((
    event: KonvaEventObject<MouseEvent | PointerEvent>,
    options: { allowEmpty?: boolean } = {},
  ) => {
    const native = event.evt;
    const middle = native.button === 1;
    const left = native.button === 0;
    const onEmpty = event.target === event.target.getStage();
    const wantsPan =
      middle ||
      (left && (spaceDown.current || native.altKey || (Boolean(options.allowEmpty) && onEmpty)));
    if (!wantsPan) return false;

    native.preventDefault();
    panning.current = {
      lastX: native.clientX,
      lastY: native.clientY,
      moved: false,
    };
    const stage = event.target.getStage();
    if (stage) stage.container().style.cursor = 'grabbing';
    return true;
  }, []);

  const onPanMove = useCallback((event: KonvaEventObject<MouseEvent | PointerEvent>) => {
    const state = panning.current;
    if (!state) return;
    const native = event.evt;
    const dx = native.clientX - state.lastX;
    const dy = native.clientY - state.lastY;
    if (dx !== 0 || dy !== 0) state.moved = true;
    state.lastX = native.clientX;
    state.lastY = native.clientY;
    setViewport((current) => ({
      ...current,
      x: current.x + dx,
      y: current.y + dy,
    }));
  }, []);

  const endPan = useCallback((event?: KonvaEventObject<MouseEvent | PointerEvent>) => {
    const state = panning.current;
    panning.current = null;
    const stage = event?.target.getStage();
    if (stage) stage.container().style.cursor = spaceDown.current ? 'grab' : '';
    return state?.moved ?? false;
  }, []);

  const isPanning = () => panning.current !== null;

  const zoomBy = useCallback((factor: number) => {
    setViewport((current) => {
      const scale = clampScale(current.scale * factor);
      if (scale === current.scale) return current;
      const cx = size.width / 2;
      const cy = size.height / 2;
      const worldX = (cx - current.x) / current.scale;
      const worldY = (cy - current.y) / current.scale;
      return { scale, x: cx - worldX * scale, y: cy - worldY * scale };
    });
  }, [size.height, size.width]);

  const resetView = useCallback(() => {
    if (size.width <= 0 || size.height <= 0 || contentWidth <= 0 || contentHeight <= 0) return;
    setViewport(fitViewport(contentWidth, contentHeight, size.width, size.height));
  }, [contentHeight, contentWidth, size.height, size.width]);

  return {
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
  };
}
