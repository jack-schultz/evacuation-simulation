import { useEffect, useMemo, useState } from 'react';
import type { BuildingLayout, EditorTool, Selection } from '../../types/building';
import { polygonArea, samePoint, uid, type Point } from '../../utils';
import { toFlatPoints } from './geometryHelpers';

const SPACE_TOOLS: EditorTool[] = ['room', 'stairs'];

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
    SPACE_TOOLS,
  };
}
