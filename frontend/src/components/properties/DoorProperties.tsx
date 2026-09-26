import type { BuildingLayout, Door } from '../../types/building';

interface Props {
  layout: BuildingLayout;
  door: Door;
  onChange: (layout: BuildingLayout) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

export function DoorProperties({ layout, door, onChange, onDeleteSelected, disabled }: Props) {
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
