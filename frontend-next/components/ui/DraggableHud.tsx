"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

const EDGE = 8;
const TOP = 52;

function snapToEdge(
  x: number,
  y: number,
  w: number,
  h: number,
  vw: number,
  vh: number,
): { x: number; y: number } {
  const left = EDGE;
  const right = Math.max(EDGE, vw - w - EDGE);
  const top = TOP;
  const bottom = Math.max(TOP, vh - h - EDGE);
  const cx = (left + right) / 2;
  const cy = (top + bottom) / 2;
  const anchors = [
    { x: left, y: top },
    { x: cx, y: top },
    { x: right, y: top },
    { x: left, y: cy },
    { x: right, y: cy },
    { x: left, y: bottom },
    { x: cx, y: bottom },
    { x: right, y: bottom },
  ];
  let best = anchors[0];
  let bestD = Infinity;
  for (const a of anchors) {
    const d = (a.x - x) ** 2 + (a.y - y) ** 2;
    if (d < bestD) {
      bestD = d;
      best = a;
    }
  }
  return best;
}

export function DraggableHud({
  storageKey,
  defaultX,
  defaultY,
  snapToEdges = false,
  children,
}: {
  storageKey: string;
  defaultX: number;
  defaultY: number;
  snapToEdges?: boolean;
  children: ReactNode;
}) {
  const [pos, setPos] = useState({ x: defaultX, y: defaultY });
  const [animating, setAnimating] = useState(false);
  const posRef = useRef(pos);
  const boxRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ dx: number; dy: number } | null>(null);

  useEffect(() => {
    posRef.current = pos;
  }, [pos]);

  const persist = useCallback(
    (next: { x: number; y: number }) => {
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // ignore
      }
    },
    [storageKey],
  );

  const applySnap = useCallback(
    (raw: { x: number; y: number }, animate: boolean) => {
      if (!snapToEdges) {
        setPos(raw);
        persist(raw);
        return raw;
      }
      const box = boxRef.current?.getBoundingClientRect();
      const w = box?.width || 88;
      const h = box?.height || 56;
      const next = snapToEdge(raw.x, raw.y, w, h, window.innerWidth, window.innerHeight);
      if (animate) setAnimating(true);
      posRef.current = next;
      setPos(next);
      persist(next);
      return next;
    },
    [persist, snapToEdges],
  );

  useEffect(() => {
    let stored: { x: number; y: number } | null = null;
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as { x?: number; y?: number };
        if (typeof parsed.x === "number" && typeof parsed.y === "number") stored = { x: parsed.x, y: parsed.y };
      }
    } catch {
      // ignore
    }
    const start = stored ?? { x: defaultX, y: defaultY };
    requestAnimationFrame(() => applySnap(start, false));
  }, [applySnap, defaultX, defaultY, storageKey]);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest("button, input, select")) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setAnimating(false);
    drag.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y };
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    const next = {
      x: Math.max(EDGE, Math.min(window.innerWidth - 48, e.clientX - drag.current.dx)),
      y: Math.max(TOP, Math.min(window.innerHeight - 48, e.clientY - drag.current.dy)),
    };
    posRef.current = next;
    setPos(next);
  };

  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    drag.current = null;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // ignore
    }
    applySnap(posRef.current, true);
  };

  return (
    <div
      ref={boxRef}
      role="group"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onTransitionEnd={() => setAnimating(false)}
      className={`fixed z-[60] cursor-grab touch-none active:cursor-grabbing ${
        animating ? "transition-[left,top] duration-300 ease-out" : ""
      }`}
      style={{ left: pos.x, top: pos.y }}
    >
      {children}
    </div>
  );
}
