import { useEffect, useRef, useState } from 'react';
import { FloodPanel } from './components/FloodPanel';
import { EmergencyPanel } from './components/EmergencyPanel';
import { BuildingCanvas } from './components/BuildingCanvas';
import { ColumnResizer } from './components/ColumnResizer';
import { FloorPlanLibrary } from './components/FloorPlanLibrary';
import { FloorStrip } from './components/FloorStrip';
import { AppHeader } from './components/AppHeader';
import { PanelRail, type PanelId } from './components/PanelRail';
import { PropertiesPanel } from './components/PropertiesPanel';
import { ResultsPanel } from './components/ResultsPanel';
import { SimulationControls } from './components/SimulationControls';
import { ToolPalette } from './components/ToolPalette';
import { downloadLayoutFile, readLayoutFile } from './layout/layoutFile';
import { useBuildingEditor } from './hooks/useBuildingEditor';
import { useBuildingPersistence } from './hooks/useBuildingPersistence';
import { useSimulationSession } from './hooks/useSimulationSession';
import { activeFloorId as resolveActiveFloorId } from './layout/emptyLayout';

const DEFAULT_OPEN: PanelId[] = ['tools'];

export default function App() {
  const mainRef = useRef<HTMLDivElement>(null);
  const [columnWidths, setColumnWidths] = useState({ tools: 260, properties: 260, library: 260 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPaths, setShowPaths] = useState(false);
  const [openPanels, setOpenPanels] = useState<Set<PanelId>>(() => new Set(DEFAULT_OPEN));
  const [activeFloorId, setActiveFloorId] = useState('floor-0');

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

  useEffect(() => {
    setActiveFloorId((current) => resolveActiveFloorId(editor.layout, current));
  }, [editor.layout.floors, editor.layout]);

  const liveEvacuated = session.playback.currentFrame
    ? session.playback.currentFrame.occupants.filter((o) => o.status === 'evacuated').length
    : null;

  const togglePanel = (id: PanelId) => {
    setOpenPanels((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const resizeColumn = (column: keyof typeof columnWidths, delta: number) => {
    const available = mainRef.current?.clientWidth ?? 1100;
    const inspectorVisible = editor.selected.length > 0;
    const toolsVisible = openPanels.size > 0;
    setColumnWidths((current) => {
      const otherWidths =
        (column !== 'tools' && toolsVisible ? 44 + current.tools : 0)
        + (column !== 'properties' && inspectorVisible ? current.properties : 0)
        + (column !== 'library' ? current.library : 0);
      const railWidth = column === 'tools' ? 44 : 0;
      const minWidth = column === 'library' ? 200 : 180;
      const maxWidth = Math.max(minWidth, available - otherWidths - railWidth - 280);
      return {
        ...current,
        [column]: Math.min(maxWidth, Math.max(minWidth, current[column] + delta)),
      };
    });
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
        onNew={persistence.onNew}
        onUndo={editor.onUndo}
        canUndo={editor.undoHistory.length > 0}
        onSave={persistence.onSave}
        dirty={editor.dirty}
        onImportFloorPlan={persistence.onImportFloorPlan}
        onImportLayout={onImportLayoutFile}
        onExportLayout={() => downloadLayoutFile(editor.layout)}
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
        evacuatedCount={liveEvacuated}
        showPaths={showPaths}
        onShowPathsChange={setShowPaths}
        error={error}
      />

      <div
        className="main"
        ref={mainRef}
        style={{
          gridTemplateColumns: `${openPanels.size > 0 ? 44 + columnWidths.tools : 44}px minmax(280px, 1fr) ${editor.selected.length > 0 ? columnWidths.properties : 0}px ${columnWidths.library}px`,
        }}
      >
        <PanelRail
          openPanels={openPanels}
          onToggle={togglePanel}
          panelWidth={columnWidths.tools}
          onResize={(delta) => resizeColumn('tools', delta)}
          panels={{
            tools: (
              <ToolPalette
                tool={editor.tool}
                onToolChange={editor.setTool}
                disabled={disabled}
              />
            ),
            flood: (
              <FloodPanel layout={editor.layout} onChange={editor.updateLayout} disabled={disabled} />
            ),
            fire: (
              <EmergencyPanel
                kind="fire"
                layout={editor.layout}
                onChange={editor.updateLayout}
                disabled={disabled}
                activeFloorId={activeFloorId}
              />
            ),
          }}
        />

        <main className="canvas-area">
          <FloorStrip
            layout={editor.layout}
            activeFloorId={activeFloorId}
            onActiveFloorChange={setActiveFloorId}
            onChange={editor.updateLayout}
            disabled={disabled}
          />
          <BuildingCanvas
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
            occupants={session.playback.currentFrame?.occupants ?? []}
            routeOccupants={session.playback.results?.occupants ?? []}
            showPaths={showPaths}
            congestedIds={session.congestedIds}
            interactive={!disabled}
            occupantRadiusM={session.occupantRadiusM}
            floodRadiusM={session.playback.currentFrame?.flood_radius_m}
            fireRadiusM={session.playback.currentFrame?.fire_radius_m}
            fireFloors={session.playback.currentFrame?.fire_floors ?? []}
            smokeFloors={session.playback.currentFrame?.smoke_floors ?? []}
            activeFloorId={activeFloorId}
          />
        </main>

        {editor.selected.length > 0 && (
          <aside className="inspector-sidebar" aria-label="Properties" style={{ width: columnWidths.properties }}>
            <ColumnResizer
              label="Resize properties panel"
              side="left"
              direction={-1}
              onResize={(delta) => resizeColumn('properties', delta)}
            />
            <PropertiesPanel
              layout={editor.layout}
              selected={editor.selected}
              onChange={editor.updateLayout}
              onSelect={editor.setSelected}
              onDeleteSelected={editor.onDeleteSelected}
              disabled={disabled}
            />
          </aside>
        )}

        <FloorPlanLibrary
          images={persistence.floorPlans}
          selectedId={persistence.selectedFloorPlanId}
          opacity={persistence.floorPlanOpacity}
          onSelect={persistence.setSelectedFloorPlanId}
          onOpacityChange={persistence.setFloorPlanOpacity}
          width={columnWidths.library}
          onResize={(delta) => resizeColumn('library', delta)}
        />

      </div>

      <ResultsPanel
        results={session.playback.results}
        evacuatedCount={liveEvacuated}
      />
    </div>
  );
}
