"use client";

import { useRaceStore } from "@/store/raceStore";

const SPEEDS: (1 | 2 | 4 | 8 | 16 | 25 | 50)[] = [1, 2, 4, 8, 16, 25, 50];

export function PlaybackControls() {
  const consoleMode = useRaceStore((s) => s.consoleMode);
  const currentLap = useRaceStore((s) => s.currentLap);
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const isPlaying = useRaceStore((s) => s.isPlaying);
  const playbackSpeed = useRaceStore((s) => s.playbackSpeed);
  const racePhase = useRaceStore((s) => s.racePhase);
  const setIsPlaying = useRaceStore((s) => s.setIsPlaying);
  const setPlaybackSpeed = useRaceStore((s) => s.setPlaybackSpeed);
  const setCurrentLap = useRaceStore((s) => s.setCurrentLap);
  const scZones = useRaceStore((s) => s.scZones);

  const isLive = consoleMode === "live";
  const scrubberZones = scZones.length
    ? scZones
    : [{ startLap: 12, endLap: 15, kind: "SC" as const }];

  return (
    <div className="flex shrink-0 flex-col gap-2 border-t border-border bg-surface-2 px-3 py-2">
      {!isLive && (
        <div className="flex items-center gap-2">
          <button
            className="rounded px-2 py-1 font-mono-data text-xs text-muted hover:bg-surface hover:text-white"
            onClick={() => setCurrentLap(Math.max(1, currentLap - 1))}
            title="Back 1 lap"
          >
            ◀◀
          </button>
          <button
            className="rounded bg-surface px-3 py-1 font-mono-data text-xs text-white hover:bg-border"
            onClick={() => setIsPlaying(!isPlaying)}
            title="Play / pause"
          >
            {isPlaying ? "⏸" : "⏯"}
          </button>
          <button
            className="rounded px-2 py-1 font-mono-data text-xs text-muted hover:bg-surface hover:text-white"
            onClick={() => setCurrentLap(Math.min(totalLaps, currentLap + 1))}
            title="Forward 1 lap"
          >
            ▶▶
          </button>
          <div className="ml-2 flex gap-1">
            {SPEEDS.map((s) => (
              <button
                key={s}
                onClick={() => setPlaybackSpeed(s)}
                className={`rounded px-1.5 py-0.5 font-mono-data text-[11px] ${
                  playbackSpeed === s ? "bg-red text-white" : "text-muted hover:text-white"
                }`}
              >
                {s}×
              </button>
            ))}
          </div>
          <div className="ml-auto font-mono-data text-xs text-white">
            Lap {currentLap} / {totalLaps}
          </div>
        </div>
      )}
      {isLive && (
        <div className="flex items-center justify-between">
          <span className="font-mono-data text-xs text-white">
            Lap {currentLap} / {totalLaps} · <span className="text-red">LIVE</span>
          </span>
          {racePhase !== "GREEN" && (
            <span className="rounded bg-amber/20 px-2 py-0.5 font-mono-data text-[11px] text-amber">
              {racePhase}
            </span>
          )}
        </div>
      )}
      <div className="relative h-3 w-full rounded-full bg-surface">
        {scrubberZones.map((z, i) => (
          <div
            key={i}
            className={`absolute top-0 h-full rounded-full ${z.kind === "RED" ? "bg-red/60" : "bg-amber/60"}`}
            style={{
              left: `${(z.startLap / totalLaps) * 100}%`,
              width: `${((z.endLap - z.startLap) / totalLaps) * 100}%`,
            }}
          />
        ))}
        <input
          type="range"
          min={1}
          max={totalLaps}
          value={currentLap}
          disabled={isLive}
          onChange={(e) => setCurrentLap(Number(e.target.value))}
          className="absolute inset-0 h-3 w-full cursor-pointer opacity-0 disabled:cursor-default"
        />
        <div
          className="pointer-events-none absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full bg-white shadow"
          style={{ left: `calc(${(currentLap / totalLaps) * 100}% - 5px)` }}
        />
      </div>
    </div>
  );
}
