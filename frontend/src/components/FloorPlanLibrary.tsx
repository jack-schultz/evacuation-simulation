import type { FloorPlanLibraryImage } from '../hooks/useBuildingPersistence';

interface Props {
  images: FloorPlanLibraryImage[];
  selectedId: string | null;
  opacity: number;
  onSelect: (id: string | null) => void;
  onOpacityChange: (opacity: number) => void;
}

export function FloorPlanLibrary({
  images,
  selectedId,
  opacity,
  onSelect,
  onOpacityChange,
}: Props) {
  return (
    <aside className="floor-plan-library" aria-label="Floor plan library">
      <h2>Library</h2>
      <p className="hint">Imported PNGs for this building. Select one to show it over the canvas.</p>
      {selectedId && (
        <div className="library-opacity">
          <label htmlFor="floor-plan-opacity">
            Overlay opacity: {Math.round(opacity * 100)}%
          </label>
          <input
            id="floor-plan-opacity"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(event) => onOpacityChange(Number(event.target.value))}
          />
          <button type="button" onClick={() => onSelect(null)}>Hide overlay</button>
        </div>
      )}
      {images.length === 0 ? (
        <p className="library-empty">No PNGs imported yet.</p>
      ) : (
        <div className="library-images">
          {images.map((image) => (
            <button
              type="button"
              key={image.id}
              className={`library-image${selectedId === image.id ? ' selected' : ''}`}
              aria-pressed={selectedId === image.id}
              onClick={() => onSelect(selectedId === image.id ? null : image.id)}
              title={`Show ${image.filename} on the canvas`}
            >
              <img src={image.url} alt="" />
              <span>{image.filename}</span>
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}
