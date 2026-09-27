import { useCallback, useEffect, useState } from 'react';
import type { BuildingLayout, EditorTool, ObjectRef, Selection } from '../types/building';
import { applySelectClick } from '../types/editor';
import { emptyLayout } from '../layout/emptyLayout';
import {
  deleteRefs,
  extractSelection,
  getClipboard,
  hasClipboard,
  offsetToWorldPoint,
  PASTE_OFFSET_M,
  pastePayload,
  setClipboard,
} from '../layout/clipboard';

export function useBuildingEditor({
  simulating,
  busy,
  setError,
  activeFloorId,
}: {
  simulating: boolean;
  busy: boolean;
  setError: (error: string | null) => void;
  activeFloorId: string;
}) {
  const [layout, setLayout] = useState<BuildingLayout>(emptyLayout());
  const [undoHistory, setUndoHistory] = useState<BuildingLayout[]>([]);
  const [tool, setTool] = useState<EditorTool>('select');
  const [selected, setSelected] = useState<Selection>([]);
  const [dirty, setDirty] = useState(false);
  const [clipboardVersion, setClipboardVersion] = useState(0);

  const updateLayout = (next: BuildingLayout) => {
    if (busy || simulating || JSON.stringify(next) === JSON.stringify(layout)) return;
    setUndoHistory((history) => [...history, layout]);
    setLayout(next);
    setDirty(true);
  };

  const onUndo = useCallback(() => {
    if (busy || simulating || undoHistory.length === 0) return;
    setLayout(undoHistory[undoHistory.length - 1]);
    setUndoHistory((history) => history.slice(0, -1));
    setSelected([]);
    setDirty(true);
    setError(null);
  }, [busy, simulating, undoHistory, setError]);

  const onDeleteSelected = useCallback(() => {
    if (selected.length === 0 || busy || simulating) return;
    updateLayout(deleteRefs(layout, selected));
    setSelected([]);
  }, [selected, busy, simulating, layout]);

  const onCopy = useCallback(() => {
    if (selected.length === 0 || busy || simulating) return;
    setClipboard(extractSelection(layout, selected));
    setClipboardVersion((v) => v + 1);
  }, [selected, busy, simulating, layout]);

  const onCut = useCallback(() => {
    if (selected.length === 0 || busy || simulating) return;
    setClipboard(extractSelection(layout, selected));
    setClipboardVersion((v) => v + 1);
    updateLayout(deleteRefs(layout, selected));
    setSelected([]);
  }, [selected, busy, simulating, layout]);

  const onPaste = useCallback(
    (worldPoint?: { x: number; y: number }) => {
      if (!hasClipboard() || busy || simulating) return;
      const payload = getClipboard();
      if (!payload) return;
      const offset = worldPoint
        ? offsetToWorldPoint(payload, worldPoint.x, worldPoint.y)
        : { x: PASTE_OFFSET_M, y: PASTE_OFFSET_M };
      const result = pastePayload(layout, payload, offset, activeFloorId);
      updateLayout(result.layout);
      setSelected(result.selection);
    },
    [busy, simulating, layout, activeFloorId],
  );

  const onDuplicate = useCallback(() => {
    if (selected.length === 0 || busy || simulating) return;
    const payload = extractSelection(layout, selected);
    const result = pastePayload(layout, payload, {
      x: PASTE_OFFSET_M,
      y: PASTE_OFFSET_M,
    }, activeFloorId);
    updateLayout(result.layout);
    setSelected(result.selection);
  }, [selected, busy, simulating, layout, activeFloorId]);

  const selectObject = useCallback(
    (
      ref: ObjectRef,
      modifiers: { shiftKey: boolean; metaKey: boolean; ctrlKey: boolean },
    ) => {
      setSelected((current) => applySelectClick(current, ref, modifiers));
    },
    [],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // Text fields retain their native text undo / clipboard behavior.
      const target = event.target;
      if (
        target instanceof HTMLElement
        && target.closest('input, textarea, select, [contenteditable]')
      ) {
        return;
      }

      const mod = event.ctrlKey || event.metaKey;
      const key = event.key.toLowerCase();

      if (event.key === 'Escape' && !mod && !event.altKey && !event.shiftKey) {
        event.preventDefault();
        setTool('select');
        return;
      }

      if (
        (event.key === 'Delete' || event.key === 'Backspace' || (key === 'q' && !mod && !event.altKey && !event.shiftKey))
        && selected.length > 0
        && !busy
        && !simulating
      ) {
        event.preventDefault();
        onDeleteSelected();
        return;
      }

      if (mod && !event.altKey) {
        if (key === 'z' && !event.shiftKey) {
          event.preventDefault();
          onUndo();
          return;
        }
        if (key === 'c' && selected.length > 0) {
          event.preventDefault();
          onCopy();
          return;
        }
        if (key === 'x' && selected.length > 0) {
          event.preventDefault();
          onCut();
          return;
        }
        if (key === 'v' && hasClipboard()) {
          event.preventDefault();
          onPaste();
          return;
        }
        if (key === 'd' && selected.length > 0) {
          event.preventDefault();
          onDuplicate();
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [
    onUndo,
    selected,
    busy,
    simulating,
    onDeleteSelected,
    onCopy,
    onCut,
    onPaste,
    onDuplicate,
  ]);

  return {
    layout,
    setLayout,
    undoHistory,
    setUndoHistory,
    tool,
    setTool,
    selected,
    setSelected,
    selectObject,
    dirty,
    setDirty,
    updateLayout,
    onUndo,
    onDeleteSelected,
    onCopy,
    onCut,
    onPaste,
    onDuplicate,
    canPaste: hasClipboard(),
    clipboardVersion,
  };
}
