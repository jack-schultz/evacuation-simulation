import type { BuildingLayout, Floor } from '../types/building';
import { DEFAULT_FLOOR_ID } from '../types/layout';
import { ensureFloors } from '../layout/emptyLayout';

interface Props {
  layout: BuildingLayout;
  activeFloorId: string;
  onActiveFloorChange: (floorId: string) => void;
  onChange: (layout: BuildingLayout) => void;
  disabled?: boolean;
}

export function FloorStrip({
  layout,
  activeFloorId,
  onActiveFloorChange,
  onChange,
  disabled,
}: Props) {
  const floors = [...ensureFloors(layout)].sort((a, b) => a.order - b.order);
  const active = floors.find((f) => f.id === activeFloorId) ?? floors[0];

  const updateFloor = (id: string, patch: Partial<Floor>) => {
    const nextFloors = ensureFloors(layout).map((f) =>
      f.id === id ? { ...f, ...patch } : f,
    );
    onChange({ ...layout, floors: nextFloors });
  };

  const addFloor = () => {
    const existing = ensureFloors(layout);
    const order = existing.reduce((m, f) => Math.max(m, f.order), -1) + 1;
    const id = `floor-${order}`;
    const elev =
      existing.reduce((m, f) => Math.max(m, f.elevation_m), -3.2) + 3.2;
    const floor: Floor = {
      id,
      name: `Level ${order}`,
      elevation_m: elev,
      order,
    };
    onChange({ ...layout, floors: [...existing, floor] });
    onActiveFloorChange(id);
  };

  return (
    <div className="floor-strip" aria-label="Building floors">
      <div className="floor-tabs">
        {floors.map((floor) => (
          <button
            key={floor.id}
            type="button"
            className={
              floor.id === activeFloorId ? 'floor-tab active' : 'floor-tab'
            }
            onClick={() => onActiveFloorChange(floor.id)}
          >
            {floor.name}
            {layout.smoke?.enabled &&
              (layout.smoke.floor_id ?? DEFAULT_FLOOR_ID) !== floor.id &&
              floor.elevation_m >
                (floors.find(
                  (f) => f.id === (layout.smoke?.floor_id ?? DEFAULT_FLOOR_ID),
                )?.elevation_m ?? 0) && (
                <span className="floor-smoke-badge" title="Smoke can rise here">
                  ↑
                </span>
              )}
          </button>
        ))}
        <button
          type="button"
          className="floor-tab add"
          disabled={disabled}
          onClick={addFloor}
          title="Add floor"
        >
          +
        </button>
      </div>
      {active && (
        <div className="floor-meta">
          <label>
            Name
            <input
              type="text"
              value={active.name}
              disabled={disabled}
              onChange={(e) => updateFloor(active.id, { name: e.target.value })}
            />
          </label>
          <label>
            Elevation (m)
            <input
              type="number"
              step="0.1"
              value={active.elevation_m}
              disabled={disabled}
              onChange={(e) => {
                const value = e.target.valueAsNumber;
                if (Number.isFinite(value)) {
                  updateFloor(active.id, { elevation_m: value });
                }
              }}
            />
          </label>
        </div>
      )}
    </div>
  );
}
