import { useRef, useState } from 'react';
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
  const mainRef = useRef<HTMLDivElement>(null);
  const [columnWidths, setColumnWidths] = useState({ tools: 200, properties: 220, hazards: 230 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
  const resizeColumn = (column: keyof typeof columnWidths, delta: number) => {
    const available = mainRef.current?.clientWidth ?? 1100;
    setColumnWidths((current) => {
      const otherWidths = Object.entries(current)
        .filter(([key]) => key !== column)
        .reduce((total, [, width]) => total + width, 0);
      const minWidth = column === 'hazards' ? 190 : 170;
      const maxWidth = Math.max(minWidth, available - otherWidths - 320);
      return { ...current, [column]: Math.min(maxWidth, Math.max(minWidth, current[column] + delta)) };
    });
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
        error={error}
      />

      <div
        className="main"
        ref={mainRef}
        style={{
          gridTemplateColumns: `${columnWidths.tools}px minmax(320px, 1fr) ${columnWidths.properties}px ${columnWidths.hazards}px`,
        }}
      >
        <aside className="sidebar tools-sidebar">
          <ColumnResizer title="Resize building tools column" direction={1}
            onResize={(delta) => resizeColumn('tools', delta)} />
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
            congestedIds={session.congestedIds}
            interactive={!disabled}
            occupantRadiusM={session.occupantRadiusM}
            floodRadiusM={session.playback.currentFrame?.flood_radius_m}
            fireRadiusM={session.playback.currentFrame?.fire_radius_m}
          />
        </main>
        <aside className="sidebar inspector-sidebar">
          <ColumnResizer title="Resize properties column" direction={-1}
            onResize={(delta) => resizeColumn('properties', delta)} />
          <PropertiesPanel
            layout={editor.layout}
            selected={editor.selected}
            onChange={editor.updateLayout}
            onDeleteSelected={editor.onDeleteSelected}
            disabled={disabled}
          />
        </aside>
        <aside className="sidebar hazards-sidebar">
          <ColumnResizer title="Resize fire and flood column" direction={-1}
            onResize={(delta) => resizeColumn('hazards', delta)} />
          <FloodPanel layout={editor.layout} onChange={editor.updateLayout} disabled={disabled} />
          <EmergencyPanel kind="fire" layout={editor.layout} onChange={editor.updateLayout} disabled={disabled} />
        </aside>
      </div>

      <ResultsPanel results={session.playback.results} />
    </div>
  );
}

function ColumnResizer({
  title,
  direction,
  onResize,
}: {
  title: string;
  direction: 1 | -1;
  onResize: (delta: number) => void;
}) {
  const previousX = useRef<number | null>(null);
  return (
    <div
      className="column-resizer"
      role="separator"
      aria-orientation="vertical"
      aria-label={title}
      tabIndex={0}
      title={title}
      onPointerDown={(event) => {
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        previousX.current = event.clientX;
      }}
      onPointerMove={(event) => {
        if (previousX.current === null) return;
        const delta = event.clientX - previousX.current;
        previousX.current = event.clientX;
        onResize(delta * direction);
      }}
      onPointerUp={() => { previousX.current = null; }}
      onPointerCancel={() => { previousX.current = null; }}
      onKeyDown={(event) => {
        if (event.key === 'ArrowLeft') onResize(-10 * direction);
        if (event.key === 'ArrowRight') onResize(10 * direction);
      }}
    />
  );
}
