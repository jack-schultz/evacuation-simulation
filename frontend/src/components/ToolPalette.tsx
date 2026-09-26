import type { EditorTool } from '../types/building';

const TOOLS: { id: EditorTool; label: string }[] = [
  { id: 'select', label: 'Select' },
  { id: 'room', label: 'Room' },
  { id: 'corridor', label: 'Corridor' },
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
        Select a tool, then click or drag on the canvas to add elements. Use Select to drag
        spaces, walls, doors, exits or the flood centre handle. Drag occupant groups into
        another space to change their location. Positions snap to the 0.5 m grid;
        door and exit connections can be changed in Properties.
      </p>
    </div>
  );
}
