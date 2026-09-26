import type { BuildingLayout, SelectedRef } from '../types/building';

interface Props {
  layout: BuildingLayout;
  selected: SelectedRef;
  onChange: (layout: BuildingLayout) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

export function PropertiesPanel({ layout, selected, onChange, onDeleteSelected, disabled }: Props) {
  if (!selected) {
    return (
      <div className="panel properties">
        <h2>Properties</h2>
        <p className="hint">Select an element to edit its properties.</p>
      </div>
    );
  }

  if (selected.kind === 'space') {
    const space = layout.spaces.find((s) => s.id === selected.id);
    if (!space) return null;
    return (
      <div className="panel properties">
        <h2>{space.type} properties</h2>
        <label>
          Name
          <input
            disabled={disabled}
            value={space.name}
            onChange={(e) =>
              onChange({
                ...layout,
                spaces: layout.spaces.map((s) =>
                  s.id === space.id ? { ...s, name: e.target.value } : s,
                ),
              })
            }
          />
        </label>
        <label>
          Width (m)
          <input
            type="number"
            step="0.5"
            min="1"
            disabled={disabled}
            value={space.width}
            onChange={(e) =>
              onChange({
                ...layout,
                spaces: layout.spaces.map((s) =>
                  s.id === space.id ? { ...s, width: Number(e.target.value) } : s,
                ),
              })
            }
          />
        </label>
        <label>
          Height (m)
          <input
            type="number"
            step="0.5"
            min="1"
            disabled={disabled}
            value={space.height}
            onChange={(e) =>
              onChange({
                ...layout,
                spaces: layout.spaces.map((s) =>
                  s.id === space.id ? { ...s, height: Number(e.target.value) } : s,
                ),
              })
            }
          />
        </label>
        <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
          Delete
        </button>
      </div>
    );
  }

  if (selected.kind === 'door') {
    const door = layout.doors.find((d) => d.id === selected.id);
    if (!door) return null;
    return (
      <div className="panel properties">
        <h2>Door properties</h2>
        <label>
          Name
          <input
            disabled={disabled}
            value={door.name}
            onChange={(e) =>
              onChange({
                ...layout,
                doors: layout.doors.map((d) =>
                  d.id === door.id ? { ...d, name: e.target.value } : d,
                ),
              })
            }
          />
        </label>
        <label>
          Width (m)
          <input
            type="number"
            step="0.1"
            min="0.5"
            disabled={disabled}
            value={door.width}
            onChange={(e) =>
              onChange({
                ...layout,
                doors: layout.doors.map((d) =>
                  d.id === door.id ? { ...d, width: Number(e.target.value) } : d,
                ),
              })
            }
          />
        </label>
        <label>
          Flow rate (occ/s)
          <input
            type="number"
            step="0.1"
            min="0.1"
            disabled={disabled}
            value={door.flow_rate_per_s ?? ''}
            placeholder="default"
            onChange={(e) =>
              onChange({
                ...layout,
                doors: layout.doors.map((d) =>
                  d.id === door.id
                    ? { ...d, flow_rate_per_s: e.target.value ? Number(e.target.value) : null }
                    : d,
                ),
              })
            }
          />
        </label>
        <label>
          Connects A
          <select
            disabled={disabled}
            value={door.connects[0]}
            onChange={(e) =>
              onChange({
                ...layout,
                doors: layout.doors.map((d) =>
                  d.id === door.id ? { ...d, connects: [e.target.value, d.connects[1]] } : d,
                ),
              })
            }
          >
            {layout.spaces.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Connects B
          <select
            disabled={disabled}
            value={door.connects[1]}
            onChange={(e) =>
              onChange({
                ...layout,
                doors: layout.doors.map((d) =>
                  d.id === door.id ? { ...d, connects: [d.connects[0], e.target.value] } : d,
                ),
              })
            }
          >
            {layout.spaces.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
          Delete
        </button>
      </div>
    );
  }

  if (selected.kind === 'exit') {
    const exit = layout.exits.find((e) => e.id === selected.id);
    if (!exit) return null;
    return (
      <div className="panel properties">
        <h2>Exit properties</h2>
        <label>
          Name
          <input
            disabled={disabled}
            value={exit.name}
            onChange={(e) =>
              onChange({
                ...layout,
                exits: layout.exits.map((x) =>
                  x.id === exit.id ? { ...x, name: e.target.value } : x,
                ),
              })
            }
          />
        </label>
        <label>
          Connected space
          <select
            disabled={disabled}
            value={exit.connected_space_id}
            onChange={(e) =>
              onChange({
                ...layout,
                exits: layout.exits.map((x) =>
                  x.id === exit.id ? { ...x, connected_space_id: e.target.value } : x,
                ),
              })
            }
          >
            {layout.spaces.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Flow rate (occ/s)
          <input
            type="number"
            step="0.1"
            min="0.1"
            disabled={disabled}
            value={exit.flow_rate_per_s ?? ''}
            onChange={(e) =>
              onChange({
                ...layout,
                exits: layout.exits.map((x) =>
                  x.id === exit.id
                    ? { ...x, flow_rate_per_s: e.target.value ? Number(e.target.value) : null }
                    : x,
                ),
              })
            }
          />
        </label>
        <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
          Delete
        </button>
      </div>
    );
  }

  if (selected.kind === 'occupants') {
    const group = layout.occupant_groups.find((g) => g.id === selected.id);
    if (!group) return null;
    return (
      <div className="panel properties">
        <h2>Occupant group</h2>
        <label>
          Name
          <input
            disabled={disabled}
            value={group.name}
            onChange={(e) =>
              onChange({
                ...layout,
                occupant_groups: layout.occupant_groups.map((g) =>
                  g.id === group.id ? { ...g, name: e.target.value } : g,
                ),
              })
            }
          />
        </label>
        <label>
          Count
          <input
            type="number"
            min="1"
            disabled={disabled}
            value={group.count}
            onChange={(e) =>
              onChange({
                ...layout,
                occupant_groups: layout.occupant_groups.map((g) =>
                  g.id === group.id ? { ...g, count: Number(e.target.value) } : g,
                ),
              })
            }
          />
        </label>
        <label>
          Location
          <select
            disabled={disabled}
            value={group.space_id}
            onChange={(e) =>
              onChange({
                ...layout,
                occupant_groups: layout.occupant_groups.map((g) =>
                  g.id === group.id ? { ...g, space_id: e.target.value } : g,
                ),
              })
            }
          >
            {layout.spaces.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Walking speed (m/s)
          <input
            type="number"
            step="0.1"
            min="0.3"
            max="3"
            disabled={disabled}
            value={group.walking_speed_mps}
            onChange={(e) =>
              onChange({
                ...layout,
                occupant_groups: layout.occupant_groups.map((g) =>
                  g.id === group.id ? { ...g, walking_speed_mps: Number(e.target.value) } : g,
                ),
              })
            }
          />
        </label>
        <label>
          Preferred exit
          <select
            disabled={disabled}
            value={group.destination_exit_id ?? ''}
            onChange={(e) =>
              onChange({
                ...layout,
                occupant_groups: layout.occupant_groups.map((g) =>
                  g.id === group.id
                    ? { ...g, destination_exit_id: e.target.value || null }
                    : g,
                ),
              })
            }
          >
            <option value="">Nearest exit</option>
            {layout.exits.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
          Delete
        </button>
      </div>
    );
  }

  if (selected.kind === 'wall') {
    const wall = layout.walls.find((w) => w.id === selected.id);
    if (!wall) return null;
    return (
      <div className="panel properties">
        <h2>Wall / obstacle</h2>
        <label>
          Name
          <input
            disabled={disabled}
            value={wall.name}
            onChange={(e) =>
              onChange({
                ...layout,
                walls: layout.walls.map((w) =>
                  w.id === wall.id ? { ...w, name: e.target.value } : w,
                ),
              })
            }
          />
        </label>
        <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
          Delete
        </button>
      </div>
    );
  }

  return null;
}
