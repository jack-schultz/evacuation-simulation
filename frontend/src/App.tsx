import { useEffect, useState } from 'react';
import { FloodPanel } from './components/FloodPanel';
import { EmergencyPanel } from './components/EmergencyPanel';
import { BuildingCanvas } from './components/BuildingCanvas';
import { AppHeader } from './components/AppHeader';
import { PanelRail, type PanelId } from './components/PanelRail';
import { PropertiesPanel } from './components/PropertiesPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { SimulationControls } from './components/SimulationControls';
import { ToolPalette } from './components/ToolPalette';
import { useBuildingEditor } from './hooks/useBuildingEditor';
import { useBuildingPersistence } from './hooks/useBuildingPersistence';
import { useSimulationSession } from './hooks/useSimulationSession';

const DEFAULT_OPEN: PanelId[] = ['tools', 'properties'];

export default function App() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPaths, setShowPaths] = useState(false);
  const [openPanels, setOpenPanels] = useState<Set<PanelId>>(() => new Set(DEFAULT_OPEN));

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

  const togglePanel = (id: PanelId) => {
    setOpenPanels((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  useEffect(() => {
    if (!editor.selected) return;
    setOpenPanels((current) => {
      if (current.has('properties')) return current;
      const next = new Set(current);
      next.add('properties');
      return next;
    });
  }, [editor.selected]);

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
        <PanelRail
          openPanels={openPanels}
          onToggle={togglePanel}
          panels={{
            tools: (
              <ToolPalette
                tool={editor.tool}
                onToolChange={editor.setTool}
                disabled={disabled}
              />
            ),
            building: (
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
            ),
            properties: (
              <PropertiesPanel
                layout={editor.layout}
                selected={editor.selected}
                onChange={editor.updateLayout}
                onSelect={editor.setSelected}
                onDeleteSelected={editor.onDeleteSelected}
                disabled={disabled}
              />
            ),
            flood: (
              <FloodPanel layout={editor.layout} onChange={editor.updateLayout} disabled={disabled} />
            ),
            fire: (
              <EmergencyPanel kind="fire" layout={editor.layout} onChange={editor.updateLayout} disabled={disabled} />
            ),
          }}
        />

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
