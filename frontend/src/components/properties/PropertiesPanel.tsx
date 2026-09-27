import type { BuildingLayout, ObjectRef, Selection } from '../../types/building';
import { primarySelection } from '../../types/editor';
import { DoorProperties } from './DoorProperties';
import { ExitProperties } from './ExitProperties';
import { OccupantGroupProperties } from './OccupantGroupProperties';
import { ObstacleProperties } from './ObstacleProperties';
import { SpaceProperties } from './SpaceProperties';

interface Props {
  layout: BuildingLayout;
  selected: Selection;
  onChange: (layout: BuildingLayout) => void;
  onSelect: (selection: Selection) => void;
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
  if (selected.length === 0) {
    return (
      <div className="panel properties">
        <h2>Properties</h2>
        <p className="hint">Select an element to edit its properties.</p>
      </div>
    );
  }

  if (selected.length > 1) {
    return (
      <div className="panel properties">
        <h2>Multiple selection</h2>
        <p className="hint">{selected.length} objects selected.</p>
        <button
          type="button"
          className="danger"
          disabled={disabled}
          onClick={onDeleteSelected}
        >
          Delete selected
        </button>
      </div>
    );
  }

  const primary = primarySelection(selected);
  if (!primary) return null;

  if (primary.kind === 'obstacle') {
    const obstacle = layout.obstacles?.find(o => o.id === primary.id);
    if (!obstacle) return null;
    return <ObstacleProperties layout={layout} obstacle={obstacle} onChange={onChange}
      onDeleteSelected={onDeleteSelected} disabled={disabled} />;
  }

  if (primary.kind === 'space') {
    const space = layout.spaces.find((s) => s.id === primary.id);
    if (!space) return null;
    return (
      <SpaceProperties
        layout={layout}
        space={space}
        onChange={onChange}
        onSelect={(ref: ObjectRef) => onSelect([ref])}
        onDeleteSelected={onDeleteSelected}
        disabled={disabled}
      />
    );
  }

  if (primary.kind === 'door') {
    const door = layout.doors.find((d) => d.id === primary.id);
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

  if (primary.kind === 'exit') {
    const exit = layout.exits.find((e) => e.id === primary.id);
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

  if (primary.kind === 'occupants') {
    const group = layout.occupant_groups.find((g) => g.id === primary.id);
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
