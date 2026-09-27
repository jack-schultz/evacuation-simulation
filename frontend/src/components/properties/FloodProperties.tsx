import type { BuildingLayout, FloodEmergency } from '../../types/building';
import { layoutFloods } from '../../layout/hazards';

interface Props {
  layout: BuildingLayout;
  flood: FloodEmergency;
  onChange: (layout: BuildingLayout) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

export function FloodProperties({
  layout,
  flood,
  onChange,
  onDeleteSelected,
  disabled,
}: Props) {
  const update = (patch: Partial<FloodEmergency>) => {
    onChange({
      ...layout,
      floods: layoutFloods(layout).map((f) => (f.id === flood.id ? { ...f, ...patch } : f)),
      flood: undefined,
    });
  };

  return (
    <div className="panel properties">
      <h2>Flood properties</h2>
      <label className="flood-toggle">
        <input
          type="checkbox"
          checked={flood.enabled}
          disabled={disabled}
          onChange={(e) => update({ enabled: e.target.checked })}
        />
        Enable flood
      </label>
      {(['x', 'y', 'radius_m'] as const).map((key) => (
        <label key={key}>
          {key === 'radius_m' ? 'Initial size / radius (m)' : `Centre ${key.toUpperCase()} (m)`}
          <input
            type="number"
            step="0.5"
            min={key === 'radius_m' ? 0.5 : 0}
            max={key === 'x' ? layout.width : key === 'y' ? layout.height : undefined}
            value={flood[key]}
            disabled={disabled}
            onChange={(e) => {
              const value = e.target.valueAsNumber;
              if (Number.isFinite(value) && e.target.validity.valid) update({ [key]: value });
            }}
          />
        </label>
      ))}
      <label>
        Rate of spread (m/s)
        <input
          type="number"
          min="0"
          step="0.01"
          value={flood.spread_speed_mps ?? 0.1}
          disabled={disabled}
          onChange={(e) => {
            const value = e.target.valueAsNumber;
            if (Number.isFinite(value) && e.target.validity.valid) {
              update({ spread_speed_mps: value });
            }
          }}
        />
      </label>
      <p className="hint">
        At this rate the flood expands {((flood.spread_speed_mps ?? 0.1) * 60).toFixed(1)} m
        per minute. Default walking speed is 1.2 m/s (72 m/min) before crowding and hazard
        slowdown. Set 0 for a fixed area.
      </p>
      <label>
        Intensity: {flood.intensity}%{' '}
        {flood.intensity === 0 ? '(no effect)' : '(slows; lethal after long immersion)'}
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          value={flood.intensity}
          disabled={disabled}
          onChange={(e) => update({ intensity: Number(e.target.value) })}
        />
      </label>
      <p className="hint">
        People prefer drier routes but may wade through flood water. Higher intensity slows
        them more. Spending roughly 10 seconds at full intensity in water (longer at lower
        intensity) becomes lethal (purple). Brief contact does not kill. Water dumps down
        stairs before spreading past them, and rises only after a floor is filled. Routes
        stay fixed.
      </p>
      <p className="hint">
        The flood expands on the same simulation clock as people. Spread speed is a scenario
        assumption; this circular model does not account for walls, slopes or water depth.
      </p>
      {disabled && <p className="hint">Reset playback to edit the flood.</p>}
      <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
        Delete
      </button>
    </div>
  );
}
