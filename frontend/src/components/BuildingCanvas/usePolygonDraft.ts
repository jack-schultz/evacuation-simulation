import { useEffect, useMemo, useState } from 'react';
import type { BuildingLayout, EditorTool, Selection } from '../../types/building';
import {
  distance,
  formatLengthM,
  polygonArea,
  samePoint,
  uid,
  type Point,
} from '../../utils';
import { toFlatPoints } from './geometryHelpers';

const SPACE_TOOLS: EditorTool[] = ['room', 'stairs'];
/** Pull length labels slightly off the edge so they stay readable. */
const LABEL_OFFSET_M = 0.35;

export type DraftLengthLabel = {
  key: string;
  x: number;
  y: number;
  text: string;
};

function lengthLabel(a: Point, b: Point, key: string): DraftLengthLabel | null {
  const len = distance(a, b);
  if (len < 1e-6) return null;
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const nx = -dy / len;
  const ny = dx / len;
  return {
    key,
    x: (a[0] + b[0]) / 2 + nx * LABEL_OFFSET_M,
    y: (a[1] + b[1]) / 2 + ny * LABEL_OFFSET_M,
    text: formatLengthM(len),
  };
}

export function usePolygonDraft({
  tool,
  interactive,
  layout,
  onChange,
  onSelect,
  activeFloorId,
}: {
  tool: EditorTool;
  interactive: boolean;
  layout: BuildingLayout;
  onChange: (layout: BuildingLayout) => void;
  onSelect: (selection: Selection) => void;
  activeFloorId: string;
}) {
  const [draftPoints, setDraftPoints] = useState<Point[]>([]);
  const [cursor, setCursor] = useState<Point | null>(null);

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

  const nearFirst = (p: Point) =>
    draftPoints.length >= 3 && samePoint(p, draftPoints[0]);

  const commitSpace = (vertices: Point[]) => {
    if (tool !== 'room' && tool !== 'stairs') return;
    if (vertices.some(([x, y]) => x < 0 || x > layout.width || y < 0 || y > layout.height)) return;
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
          capacity_density_per_m2: null,
          floor_id: activeFloorId,
        },
      ],
    });
    onSelect([{ kind: 'space', id }]);
    setDraftPoints([]);
    setCursor(null);
  };

  const cancelDraft = () => {
    setDraftPoints([]);
    setCursor(null);
  };

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

  const draftLengthLabels = useMemo(() => {
    const labels: DraftLengthLabel[] = [];
    for (let i = 1; i < draftPoints.length; i++) {
      const label = lengthLabel(draftPoints[i - 1], draftPoints[i], `edge-${i}`);
      if (label) labels.push(label);
    }
    if (draftPoints.length > 0 && cursor) {
      const end = closingPreview ? draftPoints[0] : cursor;
      const label = lengthLabel(draftPoints[draftPoints.length - 1], end, 'preview');
      if (label) labels.push(label);
    }
    return labels;
  }, [draftPoints, cursor, closingPreview]);

  return {
    draftPoints,
    setDraftPoints,
    cursor,
    setCursor,
    nearFirst,
    commitSpace,
    cancelDraft,
    closingPreview,
    draftLinePoints,
    draftLengthLabels,
    SPACE_TOOLS,
  };
}
