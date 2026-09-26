export type EditorTool =
  | 'select'
  | 'room'
  | 'corridor'
  | 'stairs'
  | 'door'
  | 'exit'
  | 'occupants'
  | 'spawn';

export type SelectedRef =
  | { kind: 'space'; id: string }
  | { kind: 'door'; id: string }
  | { kind: 'exit'; id: string }
  | { kind: 'occupants'; id: string }
  | null;
