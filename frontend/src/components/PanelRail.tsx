import type { ReactNode } from 'react';

export type PanelId = 'tools' | 'flood' | 'fire';

const PANEL_META: { id: PanelId; label: string; short: string }[] = [
  { id: 'tools', label: 'Building tools', short: 'Tools' },
  { id: 'flood', label: 'Flood emergency', short: 'Flood' },
  { id: 'fire', label: 'Fire emergency', short: 'Fire' },
];

interface Props {
  openPanels: Set<PanelId>;
  onToggle: (id: PanelId) => void;
  panels: Partial<Record<PanelId, ReactNode>>;
}

export function PanelRail({ openPanels, onToggle, panels }: Props) {
  const visible = PANEL_META.filter((p) => openPanels.has(p.id) && panels[p.id] != null);

  return (
    <div className="panel-dock">
      <nav className="panel-rail" aria-label="Panel menu">
        {PANEL_META.map((meta) => {
          const open = openPanels.has(meta.id);
          return (
            <button
              key={meta.id}
              type="button"
              className={open ? 'panel-rail-btn active' : 'panel-rail-btn'}
              aria-pressed={open}
              title={open ? `Minimise ${meta.label}` : `Expand ${meta.label}`}
              onClick={() => onToggle(meta.id)}
            >
              <span className="panel-rail-label">{meta.short}</span>
            </button>
          );
        })}
      </nav>
      {visible.length > 0 && (
        <aside className="panel-stack" aria-label="Editor panels">
          {visible.map((meta) => (
            <div key={meta.id} className="panel-stack-item">
              <button
                type="button"
                className="panel-minimize"
                title={`Minimise ${meta.label}`}
                aria-label={`Minimise ${meta.label}`}
                onClick={() => onToggle(meta.id)}
              >
                −
              </button>
              {panels[meta.id]}
            </div>
          ))}
        </aside>
      )}
    </div>
  );
}
