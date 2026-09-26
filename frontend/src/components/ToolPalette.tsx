import type { EditorTool } from '../types/building';

const TOOLS: { id: EditorTool; label: string }[] = [
  { id: 'select', label: 'Select' },
  { id: 'room', label: 'Room' },
  { id: 'stairs', label: 'Stairs' },
  { id: 'door', label: 'Door' },
  { id: 'exit', label: 'Exit' },
  { id: 'occupants', label: 'Occupants' },
];

interface Props {
  tool: EditorTool;
  onToolChange: (tool: EditorTool) => void;
  disabled?: boolean;
}

export function ToolPalette({ tool, onToolChange, disabled }: Props) {
  return (
    <div className="panel tool-palette">
      <h2>Building tools</h2>
      <div className="tool-list">
        {TOOLS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tool === t.id ? 'tool active' : 'tool'}
            disabled={disabled}
            onClick={() => onToolChange(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <p className="hint">
        Room and stairs: click corners to draw a polygon, then click the
        starting point to close it (Esc or right-click cancels). Door, exit and
        occupants place with a click. Use Select to drag spaces, doors, exits,
        occupants or hazard centres. Shift or Cmd/Ctrl+click to multi-select.
        Right-click for copy, paste, duplicate, and delete. Drag occupants to
        move their spawn point. Positions snap to the 0.5 m grid.
      </p>
    </div>
  );
}
