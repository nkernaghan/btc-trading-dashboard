'use client';

import { useRef, useCallback } from 'react';

interface ResizeHandleProps {
  direction: 'col' | 'row';
  onResize: (delta: number) => void;
}

export default function ResizeHandle({ direction, onResize }: ResizeHandleProps) {
  const draggingRef = useRef(false);
  const lastPosRef = useRef(0);
  const handleRef = useRef<HTMLDivElement>(null);

  const onMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!draggingRef.current) return;
      const current = direction === 'col' ? e.clientX : e.clientY;
      const delta = current - lastPosRef.current;
      lastPosRef.current = current;
      onResize(delta);
    },
    [direction, onResize]
  );

  const onMouseUp = useCallback(() => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    handleRef.current?.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      draggingRef.current = true;
      lastPosRef.current = direction === 'col' ? e.clientX : e.clientY;
      handleRef.current?.classList.add('dragging');
      document.body.style.cursor = direction === 'col' ? 'col-resize' : 'row-resize';
      document.body.style.userSelect = 'none';
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    },
    [direction, onMouseMove, onMouseUp]
  );

  return (
    <div
      ref={handleRef}
      className={`resize-handle resize-handle-${direction}`}
      onMouseDown={onMouseDown}
    />
  );
}
