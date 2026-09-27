import type { BuildingLayout, Obstacle } from '../../types/building';

export function ObstacleProperties({ layout, obstacle, onChange, onDeleteSelected, disabled }: {
  layout: BuildingLayout; obstacle: Obstacle; onChange: (layout: BuildingLayout) => void;
  onDeleteSelected: () => void; disabled?: boolean;
}) {
  const update = (patch: Partial<Obstacle>) => {
    const next = { ...obstacle, ...patch };
    if (next.x < 0 || next.y < 0 || next.width <= 0 || next.height <= 0
      || next.x + next.width > layout.width || next.y + next.height > layout.height) return;
    onChange({ ...layout, obstacles: (layout.obstacles ?? []).map(o => o.id === next.id ? next : o) });
  };
  return <div className="panel properties">
    <h2>Obstacle properties</h2>
    <label>Name<input disabled={disabled} value={obstacle.name}
      onChange={e => update({ name: e.target.value })} /></label>
    {(['x', 'y', 'width', 'height'] as const).map(key => <label key={key}>
      {{ x: 'X', y: 'Y', width: 'Width', height: 'Height' }[key]} (m)
      <input type="number" step="0.5" min={key === 'x' || key === 'y' ? 0 : 0.5}
        disabled={disabled} value={obstacle[key]} onChange={e => {
          const value = e.target.valueAsNumber;
          if (Number.isFinite(value)) update({ [key]: value });
        }} />
    </label>)}
    <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>Delete</button>
  </div>;
}
