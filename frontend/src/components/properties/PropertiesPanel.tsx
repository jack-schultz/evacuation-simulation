import type { BuildingLayout, SelectedRef } from '../../types/building';
import { DoorProperties } from './DoorProperties';
import { ExitProperties } from './ExitProperties';
import { OccupantGroupProperties } from './OccupantGroupProperties';
import { SpaceProperties } from './SpaceProperties';

interface Props {
  layout: BuildingLayout;
  selected: SelectedRef;
  onChange: (layout: BuildingLayout) => void;
  onSelect: (ref: SelectedRef) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

export function PropertiesPanel({
  layout,
  selected,
  onChange,
  onSelect,
  onDeleteSelected,
  disabled,
}: Props) {
  if (!selected) {
    return (
      <div className="panel properties">
        <h2>Properties</h2>
        <p className="hint">Select an element to edit its properties.</p>
      </div>
    );
  }

  if (selected.kind === 'space') {
    const space = layout.spaces.find((s) => s.id === selected.id);
    if (!space) return null;
    return (
      <SpaceProperties
        layout={layout}
        space={space}
        onChange={onChange}
        onSelect={onSelect}
        onDeleteSelected={onDeleteSelected}
        disabled={disabled}
      />
    );
  }

  if (selected.kind === 'door') {
    const door = layout.doors.find((d) => d.id === selected.id);
    if (!door) return null;
    return (
      <DoorProperties
        layout={layout}
        door={door}
        onChange={onChange}
        onDeleteSelected={onDeleteSelected}
        disabled={disabled}
      />
    );
  }

  if (selected.kind === 'exit') {
    const exit = layout.exits.find((e) => e.id === selected.id);
    if (!exit) return null;
    return (
      <ExitProperties
        layout={layout}
        exit={exit}
        onChange={onChange}
        onDeleteSelected={onDeleteSelected}
        disabled={disabled}
      />
    );
  }

  if (selected.kind === 'occupants') {
    const group = layout.occupant_groups.find((g) => g.id === selected.id);
    if (!group) return null;
    return (
      <OccupantGroupProperties
        layout={layout}
        group={group}
        onChange={onChange}
        onDeleteSelected={onDeleteSelected}
        disabled={disabled}
      />
    );
  }

  return null;
}
