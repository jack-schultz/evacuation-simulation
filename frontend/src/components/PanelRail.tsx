import type { ReactNode } from 'react';
import { ColumnResizer } from './ColumnResizer';

export type PanelId = 'tools' | 'library';

const PANEL_META: { id: PanelId; label: string; short: string }[] = [
  { id: 'tools', label: 'Building tools', short: 'Tools' },
  { id: 'library', label: 'Floor plan library', short: 'Library' },
];

interface Props {
  activePanel: PanelId | null;
  onSelect: (id: PanelId) => void;
  panels: Partial<Record<PanelId, ReactNode>>;
  panelWidth: number;
  onResize: (delta: number) => void;
}

export function PanelRail({ activePanel, onSelect, panels, panelWidth, onResize }: Props) {
  const activeMeta = PANEL_META.find((p) => p.id === activePanel);
  const content = activePanel != null ? panels[activePanel] : null;
  const visible = activeMeta != null && content != null;

  return (
    <div className="panel-dock">
      <nav className="panel-rail" aria-label="Panel menu">
        {PANEL_META.map((meta) => {
          const open = activePanel === meta.id;
          return (
            <button
              key={meta.id}
              type="button"
              className={open ? 'panel-rail-btn active' : 'panel-rail-btn'}
              aria-pressed={open}
              title={open ? `Minimise ${meta.label}` : `Show ${meta.label}`}
              onClick={() => onSelect(meta.id)}
            >
              <span className="panel-rail-label">{meta.short}</span>
            </button>
          );
        })}
      </nav>
      {visible && (
        <aside className="panel-stack" aria-label="Editor panels" style={{ width: panelWidth }}>
          <div className="panel-stack-item">
            <button
              type="button"
              className="panel-minimize"
              title={`Minimise ${activeMeta.label}`}
              aria-label={`Minimise ${activeMeta.label}`}
              onClick={() => onSelect(activeMeta.id)}
            >
              −
            </button>
            {content}
          </div>
        </aside>
      )}
      {visible && (
        <ColumnResizer
          label="Resize side panel"
          side="right"
          direction={1}
          onResize={onResize}
        />
      )}
    </div>
  );
}
