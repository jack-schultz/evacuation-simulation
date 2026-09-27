import type { BuildingSummary } from '../types/building';

interface Props {
  layoutName: string;
  onNameChange: (name: string) => void;
  buildingId: string | null;
  buildings: BuildingSummary[];
  onLoadBuilding: (id: string) => void;
  onNew: () => void;
  onUndo: () => void;
  canUndo: boolean;
  onSave: () => void;
  dirty: boolean;
  onImportFloorPlan: (file?: File) => void;
  onImportLayout: (file?: File) => void | Promise<void>;
  onExportLayout: () => void;
  busy: boolean;
  simulating: boolean;
}

export function AppHeader({
  layoutName,
  onNameChange,
  buildingId,
  buildings,
  onLoadBuilding,
  onNew,
  onUndo,
  canUndo,
  onSave,
  dirty,
  onImportFloorPlan,
  onImportLayout,
  onExportLayout,
  busy,
  simulating,
}: Props) {
  return (
    <header className="top-bar">
      <div className="brand">
        <h1>Evacuation Simulator</h1>
        <input
          className="building-name"
          value={layoutName}
          onChange={(e) => onNameChange(e.target.value)}
          disabled={busy || simulating}
        />
      </div>
      <div className="top-actions">
        <select
          value={buildingId ?? ''}
          disabled={busy}
          onChange={(e) => e.target.value && onLoadBuilding(e.target.value)}
        >
          <option value="" disabled>
            Load building…
          </option>
          {buildings.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <button type="button" onClick={onNew} disabled={busy}>
          New
        </button>
        <button
          type="button"
          onClick={onUndo}
          disabled={busy || simulating || !canUndo}
          title="Undo last building edit (Ctrl+Z / Cmd+Z)"
        >
          Undo
        </button>
        <button type="button" onClick={onSave} disabled={busy}>
          Save{dirty ? ' *' : ''}
        </button>
        <label className="file-import">
          Import JSON
          <input
            type="file"
            accept="application/json,.json"
            disabled={busy || simulating}
            onChange={(e) => {
              void onImportLayout(e.currentTarget.files?.[0]);
              e.currentTarget.value = '';
            }}
          />
        </label>
        <button type="button" onClick={onExportLayout} disabled={busy}>
          Export JSON
        </button>
        <label className="file-import">
          Import PNG
          <input
            type="file"
            accept="image/png,.png"
            disabled={busy}
            onChange={(e) => {
              void onImportFloorPlan(e.currentTarget.files?.[0]);
              e.currentTarget.value = '';
            }}
          />
        </label>
      </div>
    </header>
  );
}
