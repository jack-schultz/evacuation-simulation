import type { BuildingLayout, FireEmergency } from '../../types/building';

interface Props {
  layout: BuildingLayout;
  fire: FireEmergency;
  onChange: (layout: BuildingLayout) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

export function FireProperties({
  layout,
  fire,
  onChange,
  onDeleteSelected,
  disabled,
}: Props) {
  const update = (patch: Partial<FireEmergency>) => {
    onChange({ ...layout, fire: { ...fire, ...patch } });
  };

  return (
    <div className="panel properties">
      <h2>Fire properties</h2>
      <label className="flood-toggle">
        <input
          type="checkbox"
          checked={fire.enabled}
          disabled={disabled}
          onChange={(e) => update({ enabled: e.target.checked })}
        />
        Enable fire
      </label>
      {(['x', 'y', 'radius_m'] as const).map((key) => (
        <label key={key}>
          {key === 'radius_m' ? 'Initial size / radius (m)' : `Centre ${key.toUpperCase()} (m)`}
          <input
            type="number"
            step="0.5"
            min={key === 'radius_m' ? 0.5 : 0}
            max={key === 'x' ? layout.width : key === 'y' ? layout.height : undefined}
            value={fire[key]}
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
          value={fire.spread_speed_mps ?? 0.1}
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
        At this rate the fire expands {((fire.spread_speed_mps ?? 0.1) * 60).toFixed(1)} m
        per minute. Default walking speed is 1.2 m/s (72 m/min) before crowding and hazard
        slowdown. Set 0 for a fixed area.
      </p>
      <label>
        Intensity: {fire.intensity}%{' '}
        {fire.intensity === 0 ? '(no effect)' : '(lethal on contact)'}
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          value={fire.intensity}
          disabled={disabled}
          onChange={(e) => update({ intensity: Number(e.target.value) })}
        />
      </label>
      <p className="hint">
        People avoid entering fire and never use exits inside it. Anyone the fire touches —
        including on stairs — is trapped (purple). Smoke only slows people; it does not kill.
        Routes stay fixed.
      </p>
      <h3 className="panel-subtitle">Smoke from fire</h3>
      <label className="flood-toggle">
        <input
          type="checkbox"
          checked={fire.emit_smoke !== false}
          disabled={disabled}
          onChange={(e) => update({ emit_smoke: e.target.checked })}
        />
        Produce smoke
      </label>
      {fire.emit_smoke !== false && (
        <>
          <label>
            Smoke visibility at full intensity (m)
            <input
              type="number"
              min="1"
              step="0.5"
              value={fire.smoke_visibility_m ?? 8}
              disabled={disabled}
              onChange={(e) => {
                const value = e.target.valueAsNumber;
                if (Number.isFinite(value)) update({ smoke_visibility_m: value });
              }}
            />
          </label>
          <label>
            Stair transfer delay — smoke (s)
            <input
              type="number"
              min="0"
              step="0.5"
              value={fire.smoke_stair_spread_delay_s ?? 8}
              disabled={disabled}
              onChange={(e) => {
                const value = e.target.valueAsNumber;
                if (Number.isFinite(value)) update({ smoke_stair_spread_delay_s: value });
              }}
            />
          </label>
          <p className="hint">
            Smoke expands faster than the fire on each floor. Both spread through linked
            stairs upward and downward; fire is slower on the stairs. Smoke slows people and
            shortens sightlines but does not hard-block exits.
          </p>
        </>
      )}
      <p className="hint">
        The fire expands on the same simulation clock as people. Spread speed is a scenario
        assumption; this circular model does not account for walls, fuel, heat, or ventilation.
      </p>
      {disabled && <p className="hint">Reset playback to edit the fire.</p>}
      <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
        Delete
      </button>
    </div>
  );
}
