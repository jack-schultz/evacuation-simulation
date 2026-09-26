import { useCallback, useEffect, useMemo, useState } from 'react';
import { FloodPanel } from './components/FloodPanel';
import { BuildingCanvas } from './components/BuildingCanvas';
import { PropertiesPanel } from './components/PropertiesPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { SimulationControls } from './components/SimulationControls';
import { ToolPalette } from './components/ToolPalette';
import { api } from './services/api';
import { detectFloorPlan } from './utils/floorPlanDetection';
import { useSimulationPlayback } from './simulation/useSimulationPlayback';
import type {
  BuildingLayout,
  BuildingSummary,
  EditorTool,
  SelectedRef,
} from './types/building';

const emptyLayout = (): BuildingLayout => ({
  name: 'New Building',
  width: 40,
  height: 40,
  meters_per_cell: 1,
  spaces: [],
  doors: [],
  exits: [],
  occupant_groups: [],
});

export default function App() {
  const [buildingId, setBuildingId] = useState<string | null>(null);
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [layout, setLayout] = useState<BuildingLayout>(emptyLayout());
  const [undoHistory, setUndoHistory] = useState<BuildingLayout[]>([]);
  const [tool, setTool] = useState<EditorTool>('select');
  const [selected, setSelected] = useState<SelectedRef>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [simId, setSimId] = useState<string | null>(null);
  const [floorPlanStatus, setFloorPlanStatus] = useState<string | null>(null);
  const [floorPlanUrl, setFloorPlanUrl] = useState<string | null>(null);
  const [occupantRadiusM, setOccupantRadiusM] = useState(0.25);

  const playback = useSimulationPlayback();
  const simulating = playback.status === 'playing' || playback.status === 'paused' || playback.status === 'finished';

  const congestedIds = useMemo(() => {
    const ids = new Set<string>();
    playback.results?.congestion_hotspots.forEach((h) => ids.add(h.element_id));
    return ids;
  }, [playback.results]);

  const refreshList = useCallback(async () => {
    const list = await api.listBuildings();
    setBuildings(list);
    return list;
  }, []);

  const loadBuilding = useCallback(async (id: string) => {
    const b = await api.getBuilding(id);
    const imageUrl = await api.getFloorPlan(id);
    setFloorPlanUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return imageUrl;
    });
    setBuildingId(b.id);
    setLayout(b.layout);
    setUndoHistory([]);
    setSelected(null);
    setDirty(false);
    setFloorPlanStatus(null);
    playback.reset();
    setSimId(null);
  }, [playback]);

  useEffect(() => {
    (async () => {
      try {
        const list = await refreshList();
        if (list.length) {
          await loadBuilding(list[0].id);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateLayout = (next: BuildingLayout) => {
    if (busy || simulating || JSON.stringify(next) === JSON.stringify(layout)) return;
    setUndoHistory((history) => [...history, layout]);
    setLayout(next);
    setDirty(true);
  };

  const onUndo = useCallback(() => {
    if (busy || simulating || undoHistory.length === 0) return;
    setLayout(undoHistory[undoHistory.length - 1]);
    setUndoHistory((history) => history.slice(0, -1));
    setSelected(null);
    setDirty(true);
    setError(null);
  }, [busy, simulating, undoHistory]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // Text fields retain their native text undo behavior.
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable]')) return;
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        onUndo();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onUndo]);

  const onSave = async () => {
    setBusy(true);
    setError(null);
    try {
      if (buildingId) {
        const b = await api.updateBuilding(buildingId, layout);
        setLayout(b.layout);
        setBuildingId(b.id);
      } else {
        const b = await api.createBuilding(layout);
        setBuildingId(b.id);
        setLayout(b.layout);
      }
      setDirty(false);
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onImportFloorPlan = async (file?: File) => {
    if (!file) return;
    setError(null);
    setFloorPlanStatus(null);
    if (!file.name.toLowerCase().endsWith('.png') || (file.type && file.type !== 'image/png')) {
      setError('Choose a PNG file.');
      return;
    }
    setBusy(true);
    try {
      let id = buildingId;
      if (!id) {
        const building = await api.createBuilding(layout);
        id = building.id;
        setBuildingId(id);
        setLayout(building.layout);
        setDirty(false);
        await refreshList();
      } else if (dirty) {
        const building = await api.updateBuilding(id, layout);
        setLayout(building.layout);
        setDirty(false);
      }
      const result = await api.uploadFloorPlan(id, file);
      const imageUrl = await api.getFloorPlan(id);
      setFloorPlanUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return imageUrl;
      });
      setFloorPlanStatus(`PNG stored in database: ${result.filename}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onNew = () => {
    setBuildingId(null);
    if (floorPlanUrl) URL.revokeObjectURL(floorPlanUrl);
    setFloorPlanUrl(null);
    setLayout(emptyLayout());
    setUndoHistory([]);
    setSelected(null);
    setFloorPlanStatus(null);
    setDirty(true);
    playback.reset();
    setSimId(null);
  };

  const onDetectFloorPlan = async () => {
    if (!floorPlanUrl) return;
    try {
      setError(null);
      const image = new window.Image();
      image.src = floorPlanUrl;
      await image.decode();
      const detected = detectFloorPlan(image, layout.width, layout.height);
      if (!detected.spaces.length && !detected.walls.length) {
        throw new Error('No rooms or obstacles detected. Use enclosed white areas and separate black obstacle shapes.');
      }
      const message = `Detected ${detected.spaces.length} room rectangles and ${detected.walls.length} obstacle rectangles. Applying this map replaces current rooms, obstacles, doors, exits, occupant groups, and the previous pixel map. Continue?`;
      if (!window.confirm(message)) return;
      setLayout({ ...layout, spaces: detected.spaces, walls: detected.walls, doors: [], exits: [], occupant_groups: [], obstacle_map: detected.obstacle_map });
      setSelected(null);
      setDirty(true);
      setFloorPlanStatus(`Detected ${detected.spaces.length} rooms and ${detected.walls.length} obstacles. Add doors, exits, and occupants, then save.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onDeleteSelected = () => {
    if (!selected) return;
    if (selected.kind === 'space') {
      updateLayout({
        ...layout,
        spaces: layout.spaces.filter((s) => s.id !== selected.id),
        doors: layout.doors.filter((d) => !d.connects.includes(selected.id)),
        exits: layout.exits.filter((e) => e.connected_space_id !== selected.id),
        occupant_groups: layout.occupant_groups.filter((g) => g.space_id !== selected.id),
      });
    } else if (selected.kind === 'door') {
      updateLayout({ ...layout, doors: layout.doors.filter((d) => d.id !== selected.id) });
    } else if (selected.kind === 'exit') {
      updateLayout({ ...layout, exits: layout.exits.filter((e) => e.id !== selected.id) });
    } else if (selected.kind === 'occupants') {
      updateLayout({
        ...layout,
        occupant_groups: layout.occupant_groups.filter((g) => g.id !== selected.id),
      });
    }
    setSelected(null);
  };

  const onRun = async () => {
    setBusy(true);
    setError(null);
    try {
      let id = buildingId;
      if (!id || dirty) {
        if (id) {
          const b = await api.updateBuilding(id, layout);
          id = b.id;
          setLayout(b.layout);
        } else {
          const b = await api.createBuilding(layout);
          id = b.id;
          setBuildingId(b.id);
          setLayout(b.layout);
        }
        setDirty(false);
        await refreshList();
      }

      const created = await api.createSimulation(id, {
        timestep_s: 0.25,
        max_time_s: 600,
        frame_interval_s: 0.5,
        occupant_radius_m: 0.25,
      });
      setSimId(created.id);
      const run = await api.runSimulation(created.id);
      setOccupantRadiusM(run.parameters?.occupant_radius_m ?? 0.25);
      playback.load(run.frames, run.results);
      playback.play();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onReset = async () => {
    playback.reset();
    setOccupantRadiusM(0.25);
    if (simId) {
      try {
        await api.resetSimulation(simId);
      } catch {
        /* ignore */
      }
    }
    setSimId(null);
    setError(null);
  };

  return (
    <div className="app">
      <header className="top-bar">
        <div className="brand">
          <h1>Evacuation Simulator</h1>
          <input
            className="building-name"
            value={layout.name}
            onChange={(e) => updateLayout({ ...layout, name: e.target.value })}
            disabled={busy || simulating}
          />
        </div>
        <div className="top-actions">
          <select
            value={buildingId ?? ''}
            disabled={busy}
            onChange={(e) => e.target.value && loadBuilding(e.target.value)}
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
            disabled={busy || simulating || undoHistory.length === 0}
            title="Undo last building edit (Ctrl+Z / Cmd+Z)"
          >
            Undo
          </button>
          <button type="button" onClick={onSave} disabled={busy}>
            Save{dirty ? ' *' : ''}
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

      {floorPlanStatus && <div className="import-status" role="status">{floorPlanStatus}</div>}
      {floorPlanUrl && (
        <div className="import-status floor-plan-actions" role="note">
          <span>Black pixels block movement; white pixels are walkable. Detected rooms and obstacles are editable.</span>
          <button type="button" onClick={() => void onDetectFloorPlan()} disabled={busy}>Detect map from PNG</button>
        </div>
      )}

      <div className="disclaimer">
        Estimation tool only — not a safety certification or regulatory compliance calculation.
      </div>

      <SimulationControls
        simTime={playback.simTime}
        status={playback.status}
        speed={playback.speed}
        onSpeedChange={playback.setSpeed}
        onRun={onRun}
        onPause={playback.pause}
        onPlay={playback.play}
        onReset={onReset}
        running={busy}
        results={playback.results}
        error={error}
      />

      <div className="main">
        <aside className="sidebar">
          <ToolPalette
            tool={tool}
            onToolChange={setTool}
            disabled={busy || simulating}
          />
          <section className="panel properties">
            <h2>Building size</h2>
            {(['width', 'height'] as const).map((dimension) => (
              <label key={dimension}>
                {dimension === 'width' ? 'Width' : 'Height'} (m)
                <input
                  type="number"
                  min="1"
                  max="200"
                  step="1"
                  disabled={busy || simulating}
                  value={layout[dimension]}
                  onChange={(e) => {
                    const value = e.target.valueAsNumber;
                    if (Number.isFinite(value) && e.target.validity.valid) {
                      updateLayout({ ...layout, [dimension]: value });
                    }
                  }}
                />
              </label>
            ))}
            <p className="hint">Create another building with New, set its size and name, then Save.</p>
          </section>
          <FloodPanel layout={layout} onChange={updateLayout} disabled={busy || simulating} />
          <PropertiesPanel
            layout={layout}
            selected={selected}
            onChange={updateLayout}
            onDeleteSelected={onDeleteSelected}
            disabled={busy || simulating}
          />
        </aside>
        <main className="canvas-area">
          <BuildingCanvas
            layout={layout}
            floorPlanUrl={floorPlanUrl}
            tool={tool}
            selected={selected}
            onSelect={setSelected}
            onChange={updateLayout}
            occupants={playback.currentFrame?.occupants ?? []}
            congestedIds={congestedIds}
            interactive={!busy && !simulating}
            occupantRadiusM={occupantRadiusM}
          />
        </main>
      </div>

      <ResultsPanel results={playback.results} />
    </div>
  );
}
