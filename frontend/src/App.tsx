import { useEffect, useRef, useState } from 'react';
import { BuildingCanvas } from './components/BuildingCanvas';
import { ColumnResizer } from './components/ColumnResizer';
import { FloorPlanLibrary } from './components/FloorPlanLibrary';
import { FloorStrip } from './components/FloorStrip';
import { AppHeader } from './components/AppHeader';
import { PropertiesPanel } from './components/PropertiesPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { SimulationControls } from './components/SimulationControls';
import { ToolPalette } from './components/ToolPalette';
import { downloadLayoutFile, readLayoutFile } from './layout/layoutFile';
import { useBuildingEditor } from './hooks/useBuildingEditor';
import { useBuildingPersistence } from './hooks/useBuildingPersistence';
import { useSimulationSession } from './hooks/useSimulationSession';
import { activeFloorId as resolveActiveFloorId } from './layout/emptyLayout';

export default function App() {
  const mainRef = useRef<HTMLDivElement>(null);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPaths, setShowPaths] = useState(false);
  const [activeFloorId, setActiveFloorId] = useState('floor-0');

  const session = useSimulationSession({ setBusy, setError });
  const editor = useBuildingEditor({
    simulating: session.simulating,
    busy,
    setError,
    activeFloorId,
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
  const playbackMatchesBuilding = session.playbackBuildingId === persistence.buildingId;
  const playbackFrame = playbackMatchesBuilding ? session.playback.currentFrame : null;
  const playbackResults = playbackMatchesBuilding ? session.playback.results : null;

  useEffect(() => {
    setActiveFloorId((current) => resolveActiveFloorId(editor.layout, current));
  }, [editor.layout.floors, editor.layout]);

  const liveEvacuated = session.playback.currentFrame
    ? session.playback.currentFrame.occupants.filter((o) => o.status === 'evacuated').length
    : null;
  const liveDeaths = session.playback.currentFrame
    ? session.playback.currentFrame.occupants.filter((occupant) => occupant.deceased).length
    : null;

  const resizeSidebar = (delta: number) => {
    const available = mainRef.current?.clientWidth ?? 1100;
    setSidebarWidth((current) => Math.min(Math.max(220, available - 420), Math.max(220, current + delta)));
  };

  const onImportLayoutFile = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      persistence.onImportLayout(await readLayoutFile(file));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app">
      <AppHeader
        layoutName={editor.layout.name}
        onNameChange={(name) => editor.updateLayout({ ...editor.layout, name })}
        buildingId={persistence.buildingId}
        buildings={persistence.buildings}
        onLoadBuilding={persistence.loadBuilding}
        onImportLayout={onImportLayoutFile}
        onExportLayout={() => downloadLayoutFile(editor.layout)}
        busy={busy}
        simulating={session.simulating}
      />

      {persistence.floorPlanStatus && (
        <div className="import-status" role="status">{persistence.floorPlanStatus}</div>
      )}

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
        simulating={session.simulating}
        results={playbackResults}
        evacuatedCount={liveEvacuated}
        deathCount={liveDeaths}
        showPaths={showPaths}
        onShowPathsChange={setShowPaths}
        error={error}
      />

      <div
        className="main"
        ref={mainRef}
        style={{
          gridTemplateColumns: `${sidebarWidth}px minmax(280px, 1fr) 230px`,
        }}
      >
        <aside className="left-editor-sidebar" aria-label="Building tools and properties">
          <section className="sidebar-panel tools-panel">
            <ToolPalette
              tool={editor.tool}
              onToolChange={editor.setTool}
              disabled={disabled}
            />
          </section>
          <section className="sidebar-panel properties-panel">
            <PropertiesPanel
              layout={editor.layout}
              selected={editor.selected}
              onChange={editor.updateLayout}
              onSelect={editor.setSelected}
              onDeleteSelected={editor.onDeleteSelected}
              disabled={disabled}
            />
          </section>
          <ColumnResizer
            label="Resize tools and properties panel"
            side="right"
            direction={1}
            onResize={resizeSidebar}
          />
        </aside>

        <main className="canvas-area">
          <FloorStrip
            layout={editor.layout}
            activeFloorId={activeFloorId}
            onActiveFloorChange={setActiveFloorId}
            onChange={editor.updateLayout}
            disabled={disabled}
          />
          <BuildingCanvas
            key={persistence.buildingId ?? 'draft'}
            layout={editor.layout}
            floorPlanUrl={persistence.floorPlanUrl}
            floorPlanOpacity={persistence.floorPlanOpacity}
            tool={editor.tool}
            selected={editor.selected}
            onSelect={editor.setSelected}
            onSelectObject={editor.selectObject}
            onChange={editor.updateLayout}
            onCopy={editor.onCopy}
            onCut={editor.onCut}
            onPaste={editor.onPaste}
            onDuplicate={editor.onDuplicate}
            onDeleteSelected={editor.onDeleteSelected}
            canPaste={editor.canPaste}
            occupants={playbackFrame?.occupants ?? []}
            routeOccupants={playbackResults?.occupants ?? []}
            showPaths={showPaths}
            congestedIds={playbackMatchesBuilding ? session.congestedIds : undefined}
            interactive={!disabled}
            occupantRadiusM={session.occupantRadiusM}
            floodRadiusM={playbackFrame?.flood_radius_m}
            floodRooms={playbackFrame?.flood_rooms ?? []}
            fireRadiusM={playbackFrame?.fire_radius_m}
            fireFloors={playbackFrame?.fire_floors ?? []}
            smokeRooms={playbackFrame?.smoke_rooms ?? []}
            activeFloorId={activeFloorId}
          />
        </main>

        <div className="right-utility-column">
          <section className="panel editor-actions-panel" aria-label="Building actions">
            <div className="editor-action-grid">
              <button type="button" onClick={persistence.onNew} disabled={busy}>New</button>
              <button type="button" onClick={persistence.onSave} disabled={busy}>Save{editor.dirty ? ' *' : ''}</button>
              <button type="button" onClick={editor.onUndo} disabled={busy || session.simulating || editor.undoHistory.length === 0} title="Undo last building edit (Ctrl+Z / Cmd+Z)">Undo</button>
              <label className="file-import">
                Import PNG
                <input type="file" accept="image/png,.png" disabled={busy} onChange={(event) => {
                  void persistence.onImportFloorPlan(event.currentTarget.files?.[0]);
                  event.currentTarget.value = '';
                }} />
              </label>
            </div>
          </section>
          <FloorPlanLibrary
            images={persistence.floorPlans}
            selectedId={persistence.selectedFloorPlanId}
            opacity={persistence.floorPlanOpacity}
            onSelect={persistence.setSelectedFloorPlanId}
            onOpacityChange={persistence.setFloorPlanOpacity}
          />
        </div>
      </div>

      <ResultsPanel
        results={playbackResults}
        evacuatedCount={liveEvacuated}
      />
    </div>
  );
}
