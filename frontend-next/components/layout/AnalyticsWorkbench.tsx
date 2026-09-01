"use client";

import { catalogueEntry, renderPanel } from "@/lib/panelRegistry";
import { PanelWrapper } from "@/components/layout/PanelWrapper";

export function AnalyticsWorkbench({
  slots,
  onRemove,
}: {
  slots: string[];
  onRemove: (componentId: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-px bg-border lg:grid-cols-3">
      {slots.map((id) => {
        const entry = catalogueEntry(id);
        return (
          <section key={id} className="flex min-h-[320px] flex-col bg-carbon lg:min-h-[420px]">
            <header className="flex h-8 shrink-0 items-center justify-between border-b border-border bg-surface px-2">
              <span className="font-sans text-[11px] uppercase tracking-wide text-white">
                {entry?.label ?? id}
              </span>
              <button
                type="button"
                aria-label={`Remove ${entry?.label ?? id}`}
                onClick={() => onRemove(id)}
                className="rounded px-1.5 font-mono-data text-[11px] text-muted hover:bg-border hover:text-white"
              >
                ×
              </button>
            </header>
            <div className="min-h-0 flex-1">
              <PanelWrapper>{renderPanel(id)}</PanelWrapper>
            </div>
          </section>
        );
      })}
    </div>
  );
}
