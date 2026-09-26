import type { BuildingLayout, SelectedRef, Space } from '../../types/building';
import { polygonArea } from '../../utils';

interface Props {
  layout: BuildingLayout;
  space: Space;
  onChange: (layout: BuildingLayout) => void;
  onSelect: (ref: SelectedRef) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

function rewriteSpaceId(layout: BuildingLayout, oldId: string, newId: string): BuildingLayout {
  return {
    ...layout,
    spaces: layout.spaces.map((s) => ({
      ...s,
      id: s.id === oldId ? newId : s.id,
      linked_stair_id: s.linked_stair_id === oldId ? newId : (s.linked_stair_id ?? null),
    })),
    doors: layout.doors.map((d) => ({
      ...d,
      connects: [
        d.connects[0] === oldId ? newId : d.connects[0],
        d.connects[1] === oldId ? newId : d.connects[1],
      ] as [string, string],
    })),
    exits: layout.exits.map((x) => ({
      ...x,
      connected_space_id:
        x.connected_space_id === oldId ? newId : x.connected_space_id,
    })),
    occupant_groups: layout.occupant_groups.map((g) => ({
      ...g,
      space_id: g.space_id === oldId ? newId : g.space_id,
    })),
  };
}

function setLinkedStair(
  layout: BuildingLayout,
  spaceId: string,
  linkedId: string | null,
): BuildingLayout {
  const current = layout.spaces.find((s) => s.id === spaceId);
  const previousLinked = current?.linked_stair_id ?? null;

  return {
    ...layout,
    spaces: layout.spaces.map((s) => {
      if (s.id === spaceId) {
        return { ...s, linked_stair_id: linkedId };
      }
      if (previousLinked && s.id === previousLinked && previousLinked !== linkedId) {
        return { ...s, linked_stair_id: null };
      }
      if (linkedId && s.id === linkedId) {
        return { ...s, linked_stair_id: spaceId };
      }
      return s;
    }),
  };
}

export function SpaceProperties({
  layout,
  space,
  onChange,
  onSelect,
  onDeleteSelected,
  disabled,
}: Props) {
  const otherStairs = layout.spaces.filter(
    (s) => s.type === 'stairs' && s.id !== space.id,
  );

  const renameId = (raw: string) => {
    const newId = raw.trim();
    if (!newId || newId === space.id) return;
    if (layout.spaces.some((s) => s.id === newId)) return;
    onChange(rewriteSpaceId(layout, space.id, newId));
    onSelect({ kind: 'space', id: newId });
  };

  return (
    <div className="panel properties">
      <h2>{space.type} properties</h2>
      <label>
        Name
        <input
          disabled={disabled}
          value={space.name}
          onChange={(e) =>
            onChange({
              ...layout,
              spaces: layout.spaces.map((s) =>
                s.id === space.id ? { ...s, name: e.target.value } : s,
              ),
            })
          }
        />
      </label>
      {space.type === 'stairs' && (
        <>
          <label>
            ID
            <input
              disabled={disabled}
              defaultValue={space.id}
              key={space.id}
              onBlur={(e) => renameId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  (e.target as HTMLInputElement).blur();
                }
              }}
            />
          </label>
          <label>
            Linked stair
            <select
              disabled={disabled}
              value={space.linked_stair_id ?? ''}
              onChange={(e) =>
                onChange(setLinkedStair(layout, space.id, e.target.value || null))
              }
            >
              <option value="">None</option>
              {otherStairs.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.id})
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      <p className="hint">
        {space.vertices.length} corners · {polygonArea(space.vertices).toFixed(1)} m²
      </p>
      <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
        Delete
      </button>
    </div>
  );
}
