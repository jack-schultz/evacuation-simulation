import { useState } from 'react';
import { FloodPanel } from './components/FloodPanel';
import { EmergencyPanel } from './components/EmergencyPanel';
import { BuildingCanvas } from './components/BuildingCanvas';
import { AppHeader } from './components/AppHeader';
import { PropertiesPanel } from './components/PropertiesPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { SimulationControls } from './components/SimulationControls';
import { ToolPalette } from './components/ToolPalette';
import { useBuildingEditor } from './hooks/useBuildingEditor';
import { useBuildingPersistence } from './hooks/useBuildingPersistence';
import { useSimulationSession } from './hooks/useSimulationSession';

export default function App() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPaths, setShowPaths] = useState(false);

  const session = useSimulationSession({ setBusy, setError });
  const editor = useBuildingEditor({
    simulating: session.simulating,
    busy,
    setError,
  });
  const persistence = useBuildingPersistence({
    layout: editor.layout,
    setLayout: editor.setLayout,
    setUndoHistory: editor.setUndoHistory,
    setSelected: editor.setSelected,
    dirty: editor.dirty,
    setDirty: editor.setDirty,
    setBusy,
    setError,
    onResetSimulation: session.resetSession,
  });

  const disabled = busy || session.simulating;

  return (
    <div className="app">
      <AppHeader
        layoutName={editor.layout.name}
        onNameChange={(name) => editor.updateLayout({ ...editor.layout, name })}
        buildingId={persistence.buildingId}
        buildings={persistence.buildings}
        onLoadBuilding={persistence.loadBuilding}
        onNew={persistence.onNew}
        onUndo={editor.onUndo}
        canUndo={editor.undoHistory.length > 0}
        onSave={persistence.onSave}
        dirty={editor.dirty}
        onImportFloorPlan={persistence.onImportFloorPlan}
        busy={busy}
        simulating={session.simulating}
      />

      {persistence.floorPlanStatus && (
        <div className="import-status" role="status">{persistence.floorPlanStatus}</div>
      )}

      <div className="disclaimer">
        Estimation tool only — not a safety certification or regulatory compliance calculation.
      </div>

      <SimulationControls
        simTime={session.playback.simTime}
        status={session.playback.status}
        speed={session.playback.speed}
        onSpeedChange={session.playback.setSpeed}
        onRun={() =>
          void session.onRun({
            buildingId: persistence.buildingId,
            setBuildingId: persistence.setBuildingId,
            layout: editor.layout,
            setLayout: editor.setLayout,
            dirty: editor.dirty,
            setDirty: editor.setDirty,
            refreshList: persistence.refreshList,
          })
        }
        onPause={session.playback.pause}
        onPlay={session.playback.play}
        onReset={session.onReset}
        running={busy}
        results={session.playback.results}
        showPaths={showPaths}
        onShowPathsChange={setShowPaths}
        error={error}
      />

      <div className="main">
        <aside className="sidebar">
          <ToolPalette
            tool={editor.tool}
            onToolChange={editor.setTool}
            disabled={disabled}
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
                  disabled={disabled}
                  value={editor.layout[dimension]}
                  onChange={(e) => {
                    const value = e.target.valueAsNumber;
                    if (Number.isFinite(value) && e.target.validity.valid) {
                      editor.updateLayout({ ...editor.layout, [dimension]: value });
                    }
                  }}
                />
              </label>
            ))}
            <p className="hint">Create another building with New, set its size and name, then Save.</p>
          </section>
          <FloodPanel layout={editor.layout} onChange={editor.updateLayout} disabled={disabled} />
          <EmergencyPanel kind="fire" layout={editor.layout} onChange={editor.updateLayout} disabled={disabled} />
          <PropertiesPanel
            layout={editor.layout}
            selected={editor.selected}
            onChange={editor.updateLayout}
            onDeleteSelected={editor.onDeleteSelected}
            disabled={disabled}
          />
        </aside>
        <main className="canvas-area">
          <BuildingCanvas
            layout={editor.layout}
            floorPlanUrl={persistence.floorPlanUrl}
            tool={editor.tool}
            selected={editor.selected}
            onSelect={editor.setSelected}
            onChange={editor.updateLayout}
            occupants={session.playback.currentFrame?.occupants ?? []}
            routeOccupants={session.playback.results?.occupants ?? []}
            showPaths={showPaths}
            congestedIds={session.congestedIds}
            interactive={!disabled}
            occupantRadiusM={session.occupantRadiusM}
            floodRadiusM={session.playback.currentFrame?.flood_radius_m}
            fireRadiusM={session.playback.currentFrame?.fire_radius_m}
          />
        </main>
      </div>

      <ResultsPanel results={session.playback.results} />
    </div>
  );
}
