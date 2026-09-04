"use client";

import type { DriverListing } from "@/lib/types";

export function ArisHomeControls({
  arisOn,
  drivers,
  driver,
  onArisChange,
  onDriverChange,
}: {
  arisOn: boolean;
  drivers: DriverListing[];
  driver: string | null;
  onArisChange: (on: boolean) => void;
  onDriverChange: (code: string) => void;
}) {
  return (
    <div className="mt-3 flex flex-col gap-2">
      <div className="inline-flex w-fit overflow-hidden rounded-[8px] border border-border bg-obsidian" role="group" aria-label="ARIS toggle">
        <button
          type="button"
          aria-pressed={!arisOn}
          onClick={() => onArisChange(false)}
          className={`px-3 py-1.5 font-mono-data text-[10px] uppercase tracking-widest ${
            !arisOn ? "bg-red/15 text-red" : "text-muted hover:text-white"
          }`}
        >
          ARIS Off
        </button>
        <button
          type="button"
          aria-pressed={arisOn}
          onClick={() => onArisChange(true)}
          className={`px-3 py-1.5 font-mono-data text-[10px] uppercase tracking-widest ${
            arisOn ? "bg-red/15 text-red" : "text-muted hover:text-white"
          }`}
        >
          ARIS On
        </button>
      </div>
      {arisOn && (
        <label className="flex items-center gap-2 font-mono-data text-[10px] uppercase tracking-widest text-muted">
          Driver
          <select
            value={driver ?? ""}
            onChange={(e) => onDriverChange(e.target.value)}
            className="rounded border border-border bg-carbon px-2 py-1 text-[11px] uppercase tracking-normal text-white"
          >
            {drivers.map((d) => (
              <option key={d.driver_code} value={d.driver_code}>
                {d.driver_code} — {d.full_name}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
