import type { BuildingLayout, FloodEmergency } from '../types/building';

interface Props {
  layout: BuildingLayout;
  onChange: (layout: BuildingLayout) => void;
  disabled: boolean;
}

export function FloodPanel({ layout, onChange, disabled }: Props) {
  const flood = layout.flood;
  const update = (patch: Partial<FloodEmergency>) => {
    if (flood) onChange({ ...layout, flood: { ...flood, ...patch } });
  };
  return (
    <section className="panel properties flood-panel">
      <h2>Flood emergency</h2>
      {!flood ? (
        <button type="button" disabled={disabled} onClick={() => onChange({
          ...layout, flood: { enabled: true, x: layout.width / 2, y: layout.height / 2, radius_m: 3, intensity: 50 },
        })}>Add flood emergency</button>
      ) : (
        <>
          <label className="flood-toggle">
            <input type="checkbox" checked={flood.enabled} disabled={disabled}
              onChange={(e) => update({ enabled: e.target.checked })} /> Enable flood
          </label>
          {(['x', 'y', 'radius_m'] as const).map((key) => (
            <label key={key}>
              {key === 'radius_m' ? 'Affected radius (m)' : `Centre ${key.toUpperCase()} (m)`}
              <input type="number" step="0.5" min={key === 'radius_m' ? 0.5 : 0}
                max={key === 'x' ? layout.width : key === 'y' ? layout.height : undefined}
                value={flood[key]} disabled={disabled}
                onChange={(e) => {
                  const value = e.target.valueAsNumber;
                  if (Number.isFinite(value) && e.target.validity.valid) update({ [key]: value });
                }} />
            </label>
          ))}
          <label>
            Intensity: {flood.intensity}% {flood.intensity === 0 ? '(no effect)' : '(avoid flood)'}
            <input type="range" min="0" max="100" step="1" value={flood.intensity}
              disabled={disabled} onChange={(e) => update({ intensity: Number(e.target.value) })} />
          </label>
          <p className="hint">People avoid entering any active flood and never use flooded exits, even preferred exits. People already inside move outward along available routes; higher intensity slows their escape. Purple people have no available route.</p>
          <button type="button" className="danger" disabled={disabled}
            onClick={() => onChange({ ...layout, flood: null })}>Remove flood</button>
        </>
      )}
      <p className="hint">Illustrative intensity, not measured water depth. The flood stays fixed during a run.</p>
      {disabled && <p className="hint">Reset playback to edit the flood.</p>}
    </section>
  );
}
