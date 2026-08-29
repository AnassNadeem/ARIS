"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PANEL_CATALOGUE, type PanelCategory } from "@/lib/panelRegistry";

export function AnalyticsCatalogue({
  onAdd,
  categories = ["core", "analytics"],
}: {
  onAdd: (componentId: string) => void;
  /** Restrict which catalogue sections are shown — e.g. the console header
   * only needs "core" once analytics panels live in the extension grid. */
  categories?: PanelCategory[];
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 });
  const analytics = categories.includes("analytics") ? PANEL_CATALOGUE.filter((p) => p.category === "analytics") : [];
  const core = categories.includes("core") ? PANEL_CATALOGUE.filter((p) => p.category === "core") : [];

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const place = () => {
      const r = btnRef.current!.getBoundingClientRect();
      setMenuPos({ top: r.bottom + 6, right: Math.max(8, window.innerWidth - r.right) });
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
    <div className="relative z-50 overflow-visible">
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="rounded border border-border bg-surface px-3 py-1.5 font-mono-data text-[11px] uppercase text-white hover:border-white"
      >
        + Add ▾
      </button>
      {open &&
        createPortal(
          <>
            <div className="fixed inset-0 z-[90]" onClick={() => setOpen(false)} />
            <div
              className="fixed z-[100] w-72 max-h-[70vh] overflow-y-auto rounded-[8px] border border-border bg-surface-2 p-2 shadow-2xl"
              style={{ top: menuPos.top, right: menuPos.right }}
            >
              {core.length > 0 && (
                <>
                  <div className="px-2 py-1 font-sans text-[10px] uppercase text-muted">Core panels</div>
                  {core.map((entry) => (
                    <button
                      key={entry.componentId}
                      type="button"
                      onClick={() => {
                        onAdd(entry.componentId);
                        setOpen(false);
                      }}
                      className="flex w-full flex-col rounded px-2 py-1.5 text-left hover:bg-surface"
                    >
                      <span className="font-mono-data text-[11px] text-white">{entry.label}</span>
                      <span className="font-sans text-[10px] text-muted">{entry.description}</span>
                    </button>
                  ))}
                </>
              )}
              {analytics.length > 0 && (
                <>
                  <div className="mt-1 border-t border-border px-2 py-1 font-sans text-[10px] uppercase text-muted">
                    Analytics catalogue
                  </div>
                  {analytics.map((entry) => (
                    <button
                      key={entry.componentId}
                      type="button"
                      onClick={() => {
                        onAdd(entry.componentId);
                        setOpen(false);
                      }}
                      className="flex w-full flex-col rounded px-2 py-1.5 text-left hover:bg-surface"
                    >
                      <span className="flex items-center gap-2 font-mono-data text-[11px]">
                        <span className={entry.status === "coming-soon" ? "text-muted-2" : "text-white"}>
                          {entry.label}
                        </span>
                        {entry.status === "coming-soon" && (
                          <span className="rounded bg-carbon px-1.5 py-0.5 text-[9px] text-amber">Coming soon</span>
                        )}
                      </span>
                      <span className="font-sans text-[10px] text-muted">{entry.description}</span>
                    </button>
                  ))}
                </>
              )}
            </div>
          </>,
          document.body,
        )}
    </div>
  );
}
