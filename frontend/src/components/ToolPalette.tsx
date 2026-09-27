import type { EditorTool } from '../types/building';

const BUILDING_TOOLS: { id: EditorTool; label: string }[] = [
  { id: 'select', label: 'Select' },
  { id: 'room', label: 'Room' },
  { id: 'stairs', label: 'Stairs' },
  { id: 'obstacle', label: 'Obstacle' },
  { id: 'door', label: 'Door' },
  { id: 'exit', label: 'Exit' },
  { id: 'occupants', label: 'Occupants' },
];
const HAZARD_TOOLS: { id: EditorTool; label: string }[] = [
  { id: 'fire', label: 'Fire' },
  { id: 'flood', label: 'Flood' },
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
        {BUILDING_TOOLS.map((t) => (
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
      <h3 className="tool-category-title">Hazards</h3>
      <div className="tool-list hazard-tool-list">
        {HAZARD_TOOLS.map((t) => (
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
        starting point to close it (Esc or right-click cancels). Esc also
        switches back to Select. Door, exit, occupants, flood and fire place
        with a click (each flood/fire click adds another).
        Obstacle: click and drag a rectangle; release to place it.
        Use Select to drag spaces, obstacles, doors, exits, occupants or
        flood/fire centres. Shift or Cmd/Ctrl+click to multi-select.
        Right-click for copy, paste, duplicate, and delete. Copy on one floor
        and paste on another to reuse geometry across storeys. Hover an object
        and press E to select it. Drag occupants to move their spawn point.
        Edge lengths show while drawing rooms/stairs. Positions snap to
        the 0.5 m grid (axis-aligned edges lock near horizontal/vertical).
      </p>
    </div>
  );
}
