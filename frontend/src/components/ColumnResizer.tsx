import { useRef } from 'react';

interface Props {
  label: string;
  side: 'left' | 'right';
  /** Positive pointer movement grows the column when direction is 1. */
  direction: 1 | -1;
  onResize: (delta: number) => void;
}

export function ColumnResizer({ label, side, direction, onResize }: Props) {
  const lastX = useRef<number | null>(null);
  return (
    <div
      className={`column-resizer column-resizer-${side}`}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      tabIndex={0}
      title={label}
      onPointerDown={(event) => {
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        lastX.current = event.clientX;
      }}
      onPointerMove={(event) => {
        if (lastX.current === null) return;
        const delta = event.clientX - lastX.current;
        lastX.current = event.clientX;
        onResize(delta * direction);
      }}
      onPointerUp={() => { lastX.current = null; }}
      onPointerCancel={() => { lastX.current = null; }}
      onKeyDown={(event) => {
        if (event.key === 'ArrowLeft') onResize(-10 * direction);
        if (event.key === 'ArrowRight') onResize(10 * direction);
      }}
    />
  );
}
