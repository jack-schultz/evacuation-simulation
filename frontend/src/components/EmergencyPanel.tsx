import type { BuildingLayout, FireEmergency, RadialEmergency, SmokeEmergency } from '../types/building';

interface Props {
  kind: 'flood' | 'fire' | 'smoke';
  layout: BuildingLayout;
  onChange: (layout: BuildingLayout) => void;
  disabled: boolean;
  activeFloorId?: string;
}

export function EmergencyPanel({ kind, layout, onChange, disabled, activeFloorId }: Props) {
  const hazard = layout[kind];
  const title = kind === 'fire' ? 'Fire' : kind === 'smoke' ? 'Smoke' : 'Flood';
  const update = (patch: Partial<RadialEmergency & FireEmergency & SmokeEmergency>) => {
    if (hazard) onChange({ ...layout, [kind]: { ...hazard, ...patch } });
  };
  return (
    <section className={`panel properties ${kind}-panel`}>
      <h2>{title} emergency</h2>
      {!hazard ? (
        <button type="button" disabled={disabled} onClick={() => onChange({
          ...layout,
          [kind]: {
            enabled: true,
            x: layout.width / 2,
            y: layout.height / 2,
            radius_m: 3,
            spread_speed_mps: 0.1,
            intensity: 50,
            floor_id: activeFloorId ?? 'floor-0',
            ...(kind === 'fire' ? { emit_smoke: true } : {}),
            ...(kind === 'smoke'
              ? { visibility_m: 8, stair_spread_delay_s: 8, stair_spread_intensity_factor: 0.85 }
              : {}),
          },
        })}>Add {kind} emergency</button>
      ) : (
        <>
          <label className="flood-toggle">
            <input type="checkbox" checked={hazard.enabled} disabled={disabled}
              onChange={(e) => update({ enabled: e.target.checked })} /> Enable {kind}
          </label>
          {(['x', 'y', 'radius_m'] as const).map((key) => (
            <label key={key}>
              {key === 'radius_m' ? 'Initial size / radius (m)' : `Centre ${key.toUpperCase()} (m)`}
              <input type="number" step="0.5" min={key === 'radius_m' ? 0.5 : 0}
                max={key === 'x' ? layout.width : key === 'y' ? layout.height : undefined}
                value={hazard[key]} disabled={disabled}
                onChange={(e) => {
                  const value = e.target.valueAsNumber;
                  if (Number.isFinite(value) && e.target.validity.valid) update({ [key]: value });
                }} />
            </label>
          ))}
          <label>
            Rate of spread (m/s)
            <input type="number" min="0" step="0.01" value={hazard.spread_speed_mps ?? 0.1}
              disabled={disabled} onChange={(e) => {
                const value = e.target.valueAsNumber;
                if (Number.isFinite(value) && e.target.validity.valid) update({ spread_speed_mps: value });
              }} />
          </label>
          <p className="hint">At this rate the {kind} expands {((hazard.spread_speed_mps ?? 0.1) * 60).toFixed(1)} m per minute.
            Default walking speed is 1.2 m/s (72 m/min) before crowding and hazard slowdown. Set 0 for a fixed area.</p>
          <label>
            Intensity: {hazard.intensity}% {hazard.intensity === 0 ? '(no effect)' : kind === 'smoke' ? '(slows + cuts sight)' : `(avoid ${kind})`}
            <input type="range" min="0" max="100" step="1" value={hazard.intensity}
              disabled={disabled} onChange={(e) => update({ intensity: Number(e.target.value) })} />
          </label>
          {kind === 'smoke' && (
            <>
              <label>
                Visibility range at full intensity (m)
                <input
                  type="number"
                  min="1"
                  step="0.5"
                  value={(hazard as SmokeEmergency).visibility_m ?? 8}
                  disabled={disabled}
                  onChange={(e) => {
                    const value = e.target.valueAsNumber;
                    if (Number.isFinite(value)) update({ visibility_m: value });
                  }}
                />
              </label>
              <p className="hint">Smoke rises through linked stairs to floors above. It slows people and shortens usable sightlines; it does not hard-block exits.</p>
            </>
          )}
          {kind === 'fire' && (
            <label className="flood-toggle">
              <input
                type="checkbox"
                checked={(hazard as FireEmergency).emit_smoke !== false}
                disabled={disabled}
                onChange={(e) => update({ emit_smoke: e.target.checked })}
              />
              Emit smoke from fire
            </label>
          )}
          {kind !== 'smoke' && (
            <p className="hint">People avoid entering any active {kind} and never use affected exits, even preferred exits. People already inside move outward along available routes; higher intensity slows their escape. Routes stay fixed; people whose remaining path is affected become trapped (purple).</p>
          )}
          <button type="button" className="danger" disabled={disabled}
            onClick={() => onChange({ ...layout, [kind]: null })}>Remove {kind}</button>
        </>
      )}
      <p className="hint">The {kind} expands on the same simulation clock as people. Spread speed is a scenario assumption; this circular model does not account for walls{kind === 'fire' ? ', fuel, heat, or ventilation' : kind === 'smoke' ? ' (smoke still rises through stairs)' : ', slopes or water depth'}.</p>
      {disabled && <p className="hint">Reset playback to edit the {kind}.</p>}
    </section>
  );
}
