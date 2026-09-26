import { useEffect, useRef } from 'react';

export type ContextMenuState = {
  x: number;
  y: number;
  worldX?: number;
  worldY?: number;
  target: 'object' | 'canvas';
};

interface Props {
  state: ContextMenuState | null;
  onClose: () => void;
  canPaste: boolean;
  hasSelection: boolean;
  onDuplicate: () => void;
  onCopy: () => void;
  onCut: () => void;
  onPaste: () => void;
  onDelete: () => void;
}

export function ContextMenu({
  state,
  onClose,
  canPaste,
  hasSelection,
  onDuplicate,
  onCopy,
  onCut,
  onPaste,
  onDelete,
}: Props) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!state) return;

    const onPointerDown = (event: MouseEvent) => {
      if (menuRef.current?.contains(event.target as Node)) return;
      onClose();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    const onScroll = () => onClose();

    window.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      window.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [state, onClose]);

  if (!state) return null;

  const run = (action: () => void) => {
    action();
    onClose();
  };

  const items =
    state.target === 'canvas'
      ? [
          {
            label: 'Paste',
            disabled: !canPaste,
            onClick: () => run(onPaste),
          },
        ]
      : [
          {
            label: 'Duplicate',
            disabled: !hasSelection,
            onClick: () => run(onDuplicate),
          },
          {
            label: 'Copy',
            disabled: !hasSelection,
            onClick: () => run(onCopy),
          },
          {
            label: 'Cut',
            disabled: !hasSelection,
            onClick: () => run(onCut),
          },
          {
            label: 'Paste',
            disabled: !canPaste,
            onClick: () => run(onPaste),
          },
          {
            label: 'Delete',
            disabled: !hasSelection,
            danger: true,
            onClick: () => run(onDelete),
          },
        ];

  return (
    <div
      ref={menuRef}
      className="context-menu"
      style={{ left: state.x, top: state.y }}
      role="menu"
    >
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          role="menuitem"
          className={item.danger ? 'context-menu-item danger' : 'context-menu-item'}
          disabled={item.disabled}
          onClick={item.onClick}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
