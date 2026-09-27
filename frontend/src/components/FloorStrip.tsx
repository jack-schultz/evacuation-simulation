import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import type { BuildingLayout, Floor } from '../types/building';
import { DEFAULT_FLOOR_ID } from '../types/layout';
import { ensureFloors } from '../layout/emptyLayout';
import { deleteFloor, duplicateFloor } from '../layout/floors';

interface Props {
  layout: BuildingLayout;
  activeFloorId: string;
  onActiveFloorChange: (floorId: string) => void;
  onChange: (layout: BuildingLayout) => void;
  disabled?: boolean;
}

type FloorMenuState = {
  floorId: string;
  x: number;
  y: number;
};

export function FloorStrip({
  layout,
  activeFloorId,
  onActiveFloorChange,
  onChange,
  disabled,
}: Props) {
  const floors = [...ensureFloors(layout)].sort((a, b) => a.order - b.order);
  const active = floors.find((f) => f.id === activeFloorId) ?? floors[0];
  const [menu, setMenu] = useState<FloorMenuState | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menu) return;
    const onPointerDown = (event: MouseEvent) => {
      if (menuRef.current?.contains(event.target as Node)) return;
      setMenu(null);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenu(null);
    };
    const onScroll = () => setMenu(null);
    window.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      window.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [menu]);

  const updateFloor = (id: string, patch: Partial<Floor>) => {
    const nextFloors = ensureFloors(layout).map((f) =>
      f.id === id ? { ...f, ...patch } : f,
    );
    onChange({ ...layout, floors: nextFloors });
  };

  const addFloor = () => {
    const existing = ensureFloors(layout);
    const order = existing.reduce((m, f) => Math.max(m, f.order), -1) + 1;
    const id = `floor-${order}`;
    const elev =
      existing.reduce((m, f) => Math.max(m, f.elevation_m), -3.2) + 3.2;
    const floor: Floor = {
      id,
      name: `Level ${order}`,
      elevation_m: elev,
      order,
    };
    onChange({ ...layout, floors: [...existing, floor] });
    onActiveFloorChange(id);
  };

  const openFloorMenu = (floorId: string, event: ReactMouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    onActiveFloorChange(floorId);
    setMenu({ floorId, x: event.clientX, y: event.clientY });
  };

  const runMenu = (action: () => void) => {
    action();
    setMenu(null);
  };

  const handleDuplicate = (floorId: string) => {
    if (disabled) return;
    const result = duplicateFloor(layout, floorId);
    if (!result) return;
    onChange(result.layout);
    onActiveFloorChange(result.newFloorId);
  };

  const handleDelete = (floorId: string) => {
    if (disabled || floors.length <= 1) return;
    const next = deleteFloor(layout, floorId);
    if (!next) return;
    onChange(next);
    if (activeFloorId === floorId) {
      const remaining = [...ensureFloors(next)].sort((a, b) => a.order - b.order);
      onActiveFloorChange(remaining[0]?.id ?? DEFAULT_FLOOR_ID);
    }
  };

  const menuFloor = menu ? floors.find((f) => f.id === menu.floorId) : null;
  const canDelete = floors.length > 1;

  return (
    <div className="floor-strip" aria-label="Building floors">
      <div className="floor-tabs">
        {floors.map((floor) => (
          <button
            key={floor.id}
            type="button"
            className={
              floor.id === activeFloorId ? 'floor-tab active' : 'floor-tab'
            }
            onClick={() => onActiveFloorChange(floor.id)}
            onContextMenu={(e) => openFloorMenu(floor.id, e)}
            title="Right-click for floor options"
          >
            {floor.name}
            {layout.fire?.enabled && (() => {
              const fireFloorId = layout.fire.floor_id ?? DEFAULT_FLOOR_ID;
              const fireElev =
                floors.find((f) => f.id === fireFloorId)?.elevation_m ?? 0;
              if (floor.elevation_m > fireElev + 1e-9) {
                return (
                  <span className="floor-smoke-badge" title="Fire/smoke can rise here">
                    ↑
                  </span>
                );
              }
              if (floor.elevation_m < fireElev - 1e-9) {
                return (
                  <span className="floor-smoke-badge" title="Fire/smoke can descend here">
                    ↓
                  </span>
                );
              }
              return null;
            })()}
          </button>
        ))}
        <button
          type="button"
          className="floor-tab add"
          disabled={disabled}
          onClick={addFloor}
          title="Add floor"
        >
          +
        </button>
      </div>
      {active && (
        <div className="floor-meta">
          <label>
            Name
            <input
              type="text"
              value={active.name}
              disabled={disabled}
              onChange={(e) => updateFloor(active.id, { name: e.target.value })}
            />
          </label>
          <label>
            Elevation (m)
            <input
              type="number"
              step="0.1"
              value={active.elevation_m}
              disabled={disabled}
              onChange={(e) => {
                const value = e.target.valueAsNumber;
                if (Number.isFinite(value)) {
                  updateFloor(active.id, { elevation_m: value });
                }
              }}
            />
          </label>
        </div>
      )}
      {menu && menuFloor && (
        <div
          ref={menuRef}
          className="context-menu"
          style={{ left: menu.x, top: menu.y }}
          role="menu"
        >
          <button
            type="button"
            role="menuitem"
            className="context-menu-item"
            disabled={disabled}
            onClick={() => runMenu(() => handleDuplicate(menu.floorId))}
          >
            Duplicate floor
          </button>
          <button
            type="button"
            role="menuitem"
            className="context-menu-item danger"
            disabled={disabled || !canDelete}
            onClick={() => runMenu(() => handleDelete(menu.floorId))}
            title={!canDelete ? 'Keep at least one floor' : undefined}
          >
            Delete floor
          </button>
        </div>
      )}
    </div>
  );
}
