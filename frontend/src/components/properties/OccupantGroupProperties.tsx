import type { BuildingLayout, OccupantGroup } from '../../types/building';
import { polygonCentroid } from '../../utils';

interface Props {
  layout: BuildingLayout;
  group: OccupantGroup;
  onChange: (layout: BuildingLayout) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

export function OccupantGroupProperties({
  layout,
  group,
  onChange,
  onDeleteSelected,
  disabled,
}: Props) {
  const groupSpace = layout.spaces.find((s) => s.id === group.space_id);
  const [defaultSpawnX, defaultSpawnY] = groupSpace
    ? polygonCentroid(groupSpace.vertices)
    : [0, 0];

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
        Spawn X (m)
        <input
          type="number"
          step="0.5"
          min="0"
          disabled={disabled}
          max={layout.width}
          value={group.spawn_x ?? defaultSpawnX}
          onChange={(e) => onChange({
            ...layout,
            occupant_groups: layout.occupant_groups.map((g) =>
              g.id === group.id ? {
                ...g,
                spawn_x: Number(e.target.value),
                spawn_y: g.spawn_y ?? defaultSpawnY,
              } : g,
            ),
          })}
        />
      </label>
      <label>
        Spawn Y (m)
        <input
          type="number"
          step="0.5"
          min="0"
          disabled={disabled}
          max={layout.height}
          value={group.spawn_y ?? defaultSpawnY}
          onChange={(e) => onChange({
            ...layout,
            occupant_groups: layout.occupant_groups.map((g) =>
              g.id === group.id ? {
                ...g,
                spawn_x: g.spawn_x ?? defaultSpawnX,
                spawn_y: Number(e.target.value),
              } : g,
            ),
          })}
        />
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
