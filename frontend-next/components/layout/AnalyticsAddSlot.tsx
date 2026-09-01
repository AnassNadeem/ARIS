"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PANEL_CATALOGUE } from "@/lib/panelRegistry";

const MENU_WIDTH = 288;

export function AnalyticsAddSlot({
  onAdd,
  already,
}: {
  onAdd: (componentId: string) => void;
  already: string[];
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0, maxHeight: 320 });
  const analytics = PANEL_CATALOGUE.filter((p) => p.category === "analytics");
  const taken = new Set(already);

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const place = () => {
      const r = btnRef.current!.getBoundingClientRect();
      const left = Math.min(Math.max(8, r.left), window.innerWidth - MENU_WIDTH - 8);
      const gap = 6;
      const pad = 8;
      const spaceBelow = window.innerHeight - r.bottom - gap - pad;
      const spaceAbove = r.top - gap - pad;
      const openUp = spaceAbove > spaceBelow;
      const maxHeight = Math.max(120, openUp ? spaceAbove : spaceBelow);
      const contentH = menuRef.current?.scrollHeight || Math.min(window.innerHeight * 0.7, 420);
      const usedH = Math.min(contentH, maxHeight);
      const top = openUp ? Math.max(pad, r.top - gap - usedH) : r.bottom + gap;
      setMenuPos({ top, left, maxHeight });
    };
    place();
    const frames = [window.requestAnimationFrame(() => {
      place();
      window.requestAnimationFrame(place);
    })];
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      frames.forEach((id) => window.cancelAnimationFrame(id));
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);

  return (
    <div className="relative flex h-full min-h-[280px] items-center justify-center border border-dashed border-border bg-surface-2/60">
      <button
        ref={btnRef}
        type="button"
        aria-expanded={open}
        aria-label="Add analytics panel"
        onClick={() => setOpen((v) => !v)}
        className="flex h-16 w-16 items-center justify-center rounded-full border border-border bg-surface font-mono-data text-3xl text-white hover:border-red hover:text-red"
      >
        +
      </button>
      {open &&
        createPortal(
          <>
            <div className="fixed inset-0 z-[90]" onClick={() => setOpen(false)} />
            <div
              ref={menuRef}
              data-testid="analytics-add-menu"
              className="fixed z-[100] w-72 overflow-y-auto rounded-[8px] border border-border bg-surface-2 p-2 shadow-2xl"
              style={{ top: menuPos.top, left: menuPos.left, maxHeight: menuPos.maxHeight }}
            >
              <div className="px-2 py-1 font-sans text-[10px] uppercase text-muted">Add analytics</div>
              {analytics.map((entry) => {
                const added = taken.has(entry.componentId);
                return (
                  <button
                    key={entry.componentId}
                    type="button"
                    disabled={added}
                    onClick={() => {
                      onAdd(entry.componentId);
                      setOpen(false);
                    }}
                    className="flex w-full flex-col rounded px-2 py-1.5 text-left hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <span className="flex items-center gap-2 font-mono-data text-[11px] text-white">
                      {entry.label}
                      {added && <span className="text-[9px] uppercase text-muted">Added</span>}
                    </span>
                    <span className="font-sans text-[10px] text-muted">{entry.description}</span>
                  </button>
                );
              })}
            </div>
          </>,
          document.body,
        )}
    </div>
  );
}
