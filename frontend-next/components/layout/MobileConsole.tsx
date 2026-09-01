"use client";

import { catalogueEntry, renderPanel } from "@/lib/panelRegistry";
import { AnalyticsAddSlot } from "@/components/layout/AnalyticsAddSlot";
import { PanelWrapper } from "@/components/layout/PanelWrapper";

const CORE = ["trackmap", "timingtower", "laptimes"] as const;

export function MobileConsole({
  showComms,
  slots,
  onAdd,
  onRemove,
}: {
  showComms: boolean;
  slots: string[];
  onAdd: (componentId: string) => void;
  onRemove: (componentId: string) => void;
}) {
  const core = showComms ? [...CORE, "comms"] : [...CORE];
  return (
    <div className="flex flex-col bg-carbon">
      {core.map((id) => (
        <section
          key={id}
          className={`flex w-full flex-col border-b border-border ${
            id === "trackmap" ? "min-h-[55dvh]" : "min-h-[42dvh]"
          }`}
        >
          <header className="flex h-8 shrink-0 items-center border-b border-border bg-surface px-2">
            <span className="font-sans text-[11px] uppercase tracking-wide text-white">
              {catalogueEntry(id)?.label ?? id}
            </span>
          </header>
          <div className="min-h-0 flex-1">
            <PanelWrapper>{renderPanel(id)}</PanelWrapper>
          </div>
        </section>
      ))}
      {slots.map((id) => (
        <section key={id} className="flex min-h-[42dvh] w-full flex-col border-b border-border">
          <header className="flex h-8 shrink-0 items-center justify-between border-b border-border bg-surface px-2">
            <span className="font-sans text-[11px] uppercase tracking-wide text-white">
              {catalogueEntry(id)?.label ?? id}
            </span>
            <button
              type="button"
              aria-label={`Remove ${catalogueEntry(id)?.label ?? id}`}
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
      ))}
      <div className="min-h-[220px] border-b border-border">
        <AnalyticsAddSlot onAdd={onAdd} already={slots} />
      </div>
    </div>
  );
}
