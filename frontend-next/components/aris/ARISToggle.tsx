"use client";

import { useRaceStore } from "@/store/raceStore";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";

export function ARISToggle({ disabled, disabledReason }: { disabled?: boolean; disabledReason?: string }) {
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const arisMode = useRaceStore((s) => s.arisMode);
  const arisModeLocked = useRaceStore((s) => s.arisModeLocked);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const gridDrivers = useRaceStore((s) => s.gridDrivers);
  const setARISOn = useRaceStore((s) => s.setARISOn);
  const drivers = gridDrivers.length ? gridDrivers : MOCK_DRIVERS_2025;
  const setARISMode = useRaceStore((s) => s.setARISMode);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);

  return (
    <div className="flex flex-col gap-3">
      <button
        disabled={disabled}
        onClick={() => setARISOn(!isARISOn)}
        title={disabled ? disabledReason : undefined}
        className={`flex items-center justify-center gap-3 rounded-[8px] border px-4 py-2.5 font-mono-data text-sm transition-colors ${
          disabled
            ? "cursor-not-allowed border-border text-muted-2 opacity-50"
            : isARISOn
              ? "border-red bg-red/10 text-white"
              : "border-border text-muted hover:border-white hover:text-white"
        }`}
      >
        <span>{isARISOn ? "●" : "○"}</span>
        <span>ARIS {isARISOn ? "ON" : "OFF"}</span>
      </button>
      {disabled && disabledReason && (
        <p className="font-mono-data text-[10px] text-muted-2">{disabledReason}</p>
      )}

      {isARISOn && !disabled && (
        <div className="flex flex-col gap-3 rounded-[8px] border border-border bg-surface p-3">
          <div className="flex items-center gap-2 font-mono-data text-[11px]">
            <span className="text-muted">Mode</span>
            <div className="flex gap-1">
              {(["auto", "assisted"] as const).map((m) => (
                <button
                  key={m}
                  disabled={arisModeLocked}
                  onClick={() => setARISMode(m)}
                  title={arisModeLocked ? "Mode was chosen before the race and cannot be changed" : undefined}
                  className={`rounded px-2 py-1 uppercase ${
                    arisMode === m ? "bg-red text-white" : "bg-carbon text-muted hover:text-white"
                  } ${arisModeLocked ? "cursor-not-allowed opacity-50" : ""}`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 font-mono-data text-[11px]">
            <span className="text-muted">Driver for ARIS</span>
            <select
              value={arisDriver ?? ""}
              onChange={(e) => setARISDriver(e.target.value)}
              className="rounded border border-border bg-carbon px-2 py-1 text-white"
            >
              {drivers.map((d) => (
                <option key={d.driver_code} value={d.driver_code}>{d.driver_code} — {d.full_name}</option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
