import { useCallback, useEffect, useState } from 'react';
import type { BuildingLayout, EditorTool, SelectedRef } from '../types/building';
import { emptyLayout } from '../layout/emptyLayout';

export function useBuildingEditor({
  simulating,
  busy,
  setError,
}: {
  simulating: boolean;
  busy: boolean;
  setError: (error: string | null) => void;
}) {
  const [layout, setLayout] = useState<BuildingLayout>(emptyLayout());
  const [undoHistory, setUndoHistory] = useState<BuildingLayout[]>([]);
  const [tool, setTool] = useState<EditorTool>('select');
  const [selected, setSelected] = useState<SelectedRef>(null);
  const [dirty, setDirty] = useState(false);

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
    setSelected(null);
    setDirty(true);
    setError(null);
  }, [busy, simulating, undoHistory, setError]);

  const onDeleteSelected = useCallback(() => {
    if (!selected || busy || simulating) return;
    const apply = (next: BuildingLayout) => {
      setUndoHistory((history) => [...history, layout]);
      setLayout(next);
      setDirty(true);
    };
    if (selected.kind === 'space') {
      apply({
        ...layout,
        spaces: layout.spaces.filter((s) => s.id !== selected.id),
        doors: layout.doors.filter((d) => !d.connects.includes(selected.id)),
        exits: layout.exits.filter((e) => e.connected_space_id !== selected.id),
        occupant_groups: layout.occupant_groups.filter((g) => g.space_id !== selected.id),
      });
    } else if (selected.kind === 'door') {
      apply({ ...layout, doors: layout.doors.filter((d) => d.id !== selected.id) });
    } else if (selected.kind === 'exit') {
      apply({ ...layout, exits: layout.exits.filter((e) => e.id !== selected.id) });
    } else if (selected.kind === 'occupants') {
      apply({
        ...layout,
        occupant_groups: layout.occupant_groups.filter((g) => g.id !== selected.id),
      });
    }
    setSelected(null);
  }, [selected, busy, simulating, layout]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // Text fields retain their native text undo behavior.
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable]')) return;
      if (
        event.key.toLowerCase() === 'q'
        && !event.ctrlKey
        && !event.metaKey
        && !event.altKey
        && !event.shiftKey
        && selected
        && !busy
        && !simulating
      ) {
        event.preventDefault();
        onDeleteSelected();
        return;
      }
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        onUndo();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onUndo, selected, busy, simulating, onDeleteSelected]);

  return {
    layout,
    setLayout,
    undoHistory,
    setUndoHistory,
    tool,
    setTool,
    selected,
    setSelected,
    dirty,
    setDirty,
    updateLayout,
    onUndo,
    onDeleteSelected,
  };
}
