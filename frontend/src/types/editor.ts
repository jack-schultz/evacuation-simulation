export type EditorTool =
  | 'select'
  | 'room'
  | 'stairs'
  | 'door'
  | 'exit'
  | 'occupants';

export type SelectedRef =
  | { kind: 'space'; id: string }
  | { kind: 'door'; id: string }
  | { kind: 'exit'; id: string }
  | { kind: 'occupants'; id: string }
  | null;
