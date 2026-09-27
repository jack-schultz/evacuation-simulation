import type { BuildingLayout, Exit } from '../../types/building';

interface Props {
  layout: BuildingLayout;
  exit: Exit;
  onChange: (layout: BuildingLayout) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

export function ExitProperties({ layout, exit, onChange, onDeleteSelected, disabled }: Props) {
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
          onChange={(e) => {
            const spaceId = e.target.value;
            const host = layout.spaces.find((s) => s.id === spaceId);
            onChange({
              ...layout,
              exits: layout.exits.map((x) =>
                x.id === exit.id
                  ? {
                      ...x,
                      connected_space_id: spaceId,
                      floor_id: host?.floor_id ?? x.floor_id,
                    }
                  : x,
              ),
            });
          }}
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
