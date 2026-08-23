"use client";

import { useState, type PointerEvent as ReactPointerEvent } from "react";
import { PANEL_CATALOGUE, catalogueEntry, renderPanel } from "@/lib/panelRegistry";
import { PanelWrapper } from "@/components/layout/PanelWrapper";

interface Slot {
  id: string;
  componentId: string | null;
  height: number;
}

const LANE_COUNT = 3;
const DEFAULT_HEIGHT = 260;
const MIN_HEIGHT = 140;
const DEFAULT_SEED = ["tyredeg", "sectortimes", "gapchart"];

let slotSeq = 0;
function makeEmptySlot(): Slot {
  slotSeq += 1;
  return { id: `slot-${slotSeq}`, componentId: null, height: DEFAULT_HEIGHT };
}

function initialLanes(): Slot[][] {
  return Array.from({ length: LANE_COUNT }, (_, i) => {
    const seeded = DEFAULT_SEED[i];
    if (!seeded) return [makeEmptySlot()];
    return [{ id: `seed-${i}`, componentId: seeded, height: DEFAULT_HEIGHT }, makeEmptySlot()];
  });
}

/**
 * A below-the-fold "keep building the dashboard" area: independent vertical
 * lanes of resizable panel cells, each lane always ending in an empty
 * "+ add" cell. Dragging a filled cell's bottom edge grows it — and with it
 * the whole scrollable console — instead of a separate "grow canvas" control.
 */
export function ExtensionGrid() {
  const [lanes, setLanes] = useState<Slot[][]>(initialLanes);

  function updateLane(laneIdx: number, updater: (lane: Slot[]) => Slot[]) {
    setLanes((prev) => prev.map((lane, i) => (i === laneIdx ? updater(lane) : lane)));
  }

  function setSlotComponent(laneIdx: number, slotId: string, componentId: string) {
    updateLane(laneIdx, (lane) => {
      const next = lane.map((s) => (s.id === slotId ? { ...s, componentId } : s));
      const trailingEmpty = next.length > 0 && next[next.length - 1].componentId === null;
      return trailingEmpty ? next : [...next, makeEmptySlot()];
    });
  }

  function removeSlot(laneIdx: number, slotId: string) {
    updateLane(laneIdx, (lane) => {
      const next = lane.filter((s) => s.id !== slotId);
      const trailingEmpty = next.length > 0 && next[next.length - 1].componentId === null;
      return trailingEmpty ? next : [...next, makeEmptySlot()];
    });
  }

  function resizeSlot(laneIdx: number, slotId: string, height: number) {
    updateLane(laneIdx, (lane) => lane.map((s) => (s.id === slotId ? { ...s, height } : s)));
  }

  return (
    <div className="flex min-h-[240px] flex-1 gap-3 border-t border-border bg-carbon p-3">
      {lanes.map((lane, laneIdx) => (
        <div key={laneIdx} className="flex flex-1 flex-col gap-3">
          {lane.map((slot) => (
            <GridCell
              key={slot.id}
              slot={slot}
              onPick={(componentId) => setSlotComponent(laneIdx, slot.id, componentId)}
              onRemove={() => removeSlot(laneIdx, slot.id)}
              onResize={(h) => resizeSlot(laneIdx, slot.id, h)}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function GridCell({
  slot,
  onPick,
  onRemove,
  onResize,
}: {
  slot: Slot;
  onPick: (componentId: string) => void;
  onRemove: () => void;
  onResize: (height: number) => void;
}) {
  const [open, setOpen] = useState(false);

  function handleResizePointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = slot.height;
    function onMove(ev: PointerEvent) {
      onResize(Math.max(MIN_HEIGHT, startHeight + (ev.clientY - startY)));
    }
    function onUp() {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  if (!slot.componentId) {
    const analytics = PANEL_CATALOGUE.filter((p) => p.category === "analytics");
    return (
      <div
        style={{ height: slot.height }}
        className="relative flex shrink-0 items-center justify-center rounded-[8px] border border-dashed border-border bg-surface/40"
      >
        <button
          onClick={() => setOpen((v) => !v)}
          title="Add a section here"
          className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-lg text-muted hover:border-white hover:text-white"
        >
          +
        </button>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <div className="absolute left-1/2 top-1/2 z-50 w-64 -translate-x-1/2 -translate-y-1/2 max-h-72 overflow-y-auto rounded-[8px] border border-border bg-surface-2 p-2 shadow-2xl">
              {analytics.map((entry) => (
                <button
                  key={entry.componentId}
                  onClick={() => {
                    onPick(entry.componentId);
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

  const entry = catalogueEntry(slot.componentId);

  return (
    <div
      style={{ height: slot.height }}
      className="relative flex shrink-0 flex-col rounded-[8px] border border-border bg-surface-2"
    >
      <div className="flex h-7 shrink-0 items-center justify-between border-b border-border px-2">
        <span className="font-mono-data text-[10px] uppercase text-muted">{entry?.label ?? slot.componentId}</span>
        <button
          onClick={onRemove}
          title="Remove section"
          className="rounded px-1 text-[11px] text-muted hover:bg-border hover:text-white"
        >
          ×
        </button>
      </div>
      <div className="min-h-0 flex-1">
        <PanelWrapper>{renderPanel(slot.componentId)}</PanelWrapper>
      </div>
      <div
        onPointerDown={handleResizePointerDown}
        title="Drag to add space below"
        className="group absolute -bottom-1.5 left-0 z-10 flex h-3 w-full cursor-row-resize items-center justify-center"
      >
        <span className="h-0.5 w-8 rounded bg-muted-2 opacity-0 group-hover:opacity-100" />
      </div>
    </div>
  );
}
