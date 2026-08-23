"use client";

import { useState } from "react";
import { PANEL_CATALOGUE } from "@/lib/panelRegistry";

export function AnalyticsCatalogue({ onAdd }: { onAdd: (componentId: string) => void }) {
  const [open, setOpen] = useState(false);
  const analytics = PANEL_CATALOGUE.filter((p) => p.category === "analytics");
  const core = PANEL_CATALOGUE.filter((p) => p.category === "core");

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="rounded border border-border bg-surface px-3 py-1.5 font-mono-data text-[11px] uppercase text-white hover:border-white"
      >
        + Add ▾
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-50 mt-1 w-72 max-h-[70vh] overflow-y-auto rounded-[8px] border border-border bg-surface-2 p-2 shadow-2xl">
            <div className="px-2 py-1 font-mono-data text-[10px] uppercase text-muted">Core panels</div>
            {core.map((entry) => (
              <button
                key={entry.componentId}
                onClick={() => {
                  onAdd(entry.componentId);
                  setOpen(false);
                }}
                className="flex w-full flex-col rounded px-2 py-1.5 text-left hover:bg-surface"
              >
                <span className="font-mono-data text-[11px] text-white">{entry.label}</span>
                <span className="font-mono-data text-[10px] text-muted">{entry.description}</span>
              </button>
            ))}
            <div className="mt-1 border-t border-border px-2 py-1 font-mono-data text-[10px] uppercase text-muted">
              Analytics catalogue
            </div>
            {analytics.map((entry) => (
              <button
                key={entry.componentId}
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
                <span className="font-mono-data text-[10px] text-muted">{entry.description}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
