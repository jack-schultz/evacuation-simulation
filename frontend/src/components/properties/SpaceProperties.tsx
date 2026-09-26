import type { BuildingLayout, Space } from '../../types/building';
import { polygonArea } from '../../utils';

interface Props {
  layout: BuildingLayout;
  space: Space;
  onChange: (layout: BuildingLayout) => void;
  onDeleteSelected: () => void;
  disabled?: boolean;
}

export function SpaceProperties({ layout, space, onChange, onDeleteSelected, disabled }: Props) {
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
      <p className="hint">
        {space.vertices.length} corners · {polygonArea(space.vertices).toFixed(1)} m²
      </p>
      <button type="button" className="danger" disabled={disabled} onClick={onDeleteSelected}>
        Delete
      </button>
    </div>
  );
}
