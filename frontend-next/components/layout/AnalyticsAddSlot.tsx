"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PANEL_CATALOGUE } from "@/lib/panelRegistry";

export function AnalyticsAddSlot({
  onAdd,
  already,
}: {
  onAdd: (componentId: string) => void;
  already: string[];
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const analytics = PANEL_CATALOGUE.filter((p) => p.category === "analytics");
  const taken = new Set(already);

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const place = () => {
      const r = btnRef.current!.getBoundingClientRect();
      const width = 288;
      const left = Math.min(Math.max(8, r.left), window.innerWidth - width - 8);
      setMenuPos({ top: r.bottom + 6, left });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
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
              className="fixed z-[100] w-72 max-h-[70vh] overflow-y-auto rounded-[8px] border border-border bg-surface-2 p-2 shadow-2xl"
              style={{ top: menuPos.top, left: menuPos.left }}
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
