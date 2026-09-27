export type EditorTool =
  | 'obstacle'
  | 'select'
  | 'room'
  | 'stairs'
  | 'door'
  | 'exit'
  | 'occupants'
  | 'flood'
  | 'fire';

export type ObjectRef =
  | { kind: 'obstacle'; id: string }
  | { kind: 'space'; id: string }
  | { kind: 'door'; id: string }
  | { kind: 'exit'; id: string }
  | { kind: 'occupants'; id: string }
  | { kind: 'flood'; id: string }
  | { kind: 'fire'; id: string };

/** Currently selected objects; empty means nothing selected. */
export type Selection = ObjectRef[];

export function refsEqual(a: ObjectRef, b: ObjectRef): boolean {
  return a.kind === b.kind && a.id === b.id;
}

export function isRefSelected(selection: Selection, ref: ObjectRef): boolean {
  return selection.some((item) => refsEqual(item, ref));
}

/** Last-clicked / primary object for the single-object properties panel. */
export function primarySelection(selection: Selection): ObjectRef | null {
  return selection.length > 0 ? selection[selection.length - 1] : null;
}

/** Plain click replaces; Shift/Cmd/Ctrl toggles membership. */
export function applySelectClick(
  current: Selection,
  ref: ObjectRef,
  modifiers: { shiftKey: boolean; metaKey: boolean; ctrlKey: boolean },
): Selection {
  const toggle = modifiers.shiftKey || modifiers.metaKey || modifiers.ctrlKey;
  if (!toggle) return [ref];
  if (isRefSelected(current, ref)) {
    return current.filter((item) => !refsEqual(item, ref));
  }
  return [...current, ref];
}

/** Right-click: keep multi-selection if target already selected, else select only it. */
export function applyContextSelect(current: Selection, ref: ObjectRef): Selection {
  if (isRefSelected(current, ref)) return current;
  return [ref];
}
