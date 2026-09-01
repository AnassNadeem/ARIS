"use client";

import { useRaceStore } from "@/store/raceStore";
import { formatLapHeader } from "@/lib/formatLap";

const SPEEDS: (1 | 2 | 4 | 8 | 16 | 25 | 50)[] = [1, 2, 4, 8, 16, 25, 50];

export function PlaybackControls() {
  const consoleMode = useRaceStore((s) => s.consoleMode);
  const currentLap = useRaceStore((s) => s.currentLap);
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const isPlaying = useRaceStore((s) => s.isPlaying);
  const playbackSpeed = useRaceStore((s) => s.playbackSpeed);
  const racePhase = useRaceStore((s) => s.racePhase);
  const consolePlayState = useRaceStore((s) => s.consolePlayState);
  const setIsPlaying = useRaceStore((s) => s.setIsPlaying);
  const setPlaybackSpeed = useRaceStore((s) => s.setPlaybackSpeed);
  const seekToLap = useRaceStore((s) => s.seekToLap);
  const scZones = useRaceStore((s) => s.scZones);

  const distance = Math.max(1, totalLaps);
  const isLive = consoleMode === "live";
  const racing = isLive || consolePlayState === "racing";
  const scrubberZones = scZones;

  return (
    <div className="flex shrink-0 flex-col gap-2 border-t border-border bg-surface-2 px-4 py-2">
      {!isLive && (
        <div className="flex items-center gap-2">
          <button
            className="rounded px-2 py-1 font-mono-data text-xs text-muted hover:bg-surface hover:text-white"
            onClick={() => seekToLap(Math.max(1, currentLap - 1))}
            title="Back 1 lap"
          >
            ◀◀
          </button>
          <button
            className="rounded bg-surface px-4 py-1 font-mono-data text-xs text-white hover:bg-border disabled:cursor-not-allowed disabled:opacity-40"
            onClick={() => racing && setIsPlaying(!isPlaying)}
            disabled={!racing}
            title={racing ? "Play / pause" : "Start the race from the header first"}
          >
            {isPlaying ? "⏸" : "⏯"}
          </button>
          <button
            className="rounded px-2 py-1 font-mono-data text-xs text-muted hover:bg-surface hover:text-white"
            onClick={() => seekToLap(Math.min(distance, currentLap + 1))}
            title="Forward 1 lap"
          >
            ▶▶
          </button>
          <div className="ml-2 hidden gap-1 md:flex">
            {SPEEDS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setPlaybackSpeed(s)}
                className={`rounded px-2 py-0.5 font-mono-data text-xs ${
                  playbackSpeed === s ? "bg-red text-white" : "text-muted hover:text-white"
                }`}
              >
                {s}×
              </button>
            ))}
          </div>
          <label className="ml-2 md:hidden">
            <span className="sr-only">Playback speed</span>
            <select
              value={playbackSpeed}
              aria-label="Playback speed"
              onChange={(e) => setPlaybackSpeed(Number(e.target.value) as (typeof SPEEDS)[number])}
              className="rounded border border-border bg-surface px-2 py-1 font-mono-data text-xs text-white"
            >
              {SPEEDS.map((s) => (
                <option key={s} value={s}>
                  {s}×
                </option>
              ))}
            </select>
          </label>
          <div className="ml-auto hidden font-mono-data text-xs text-white md:block">
            {formatLapHeader(currentLap, totalLaps)}
          </div>
        </div>
      )}
      {isLive && (
        <div className="flex items-center justify-between">
          <span className="font-mono-data text-xs text-white">
            {formatLapHeader(currentLap, totalLaps)} · <span className="text-red">LIVE</span>
          </span>
          {racePhase !== "GREEN" && (
            <span className="rounded bg-amber/20 px-2 py-0.5 font-mono-data text-xs text-amber">
              {racePhase}
            </span>
          )}
        </div>
      )}
      <div className="relative h-2 w-full rounded-full bg-surface">
        {scrubberZones.map((z, i) => (
          <div
            key={i}
            className={`absolute top-0 h-full rounded-full ${z.kind === "RED_FLAG" ? "bg-red/60" : "bg-amber/60"}`}
            style={{
              left: `${(z.startLap / distance) * 100}%`,
              width: `${((z.endLap - z.startLap) / distance) * 100}%`,
            }}
          />
        ))}
        <input
          type="range"
          min={1}
          max={distance}
          value={currentLap}
          disabled={isLive}
          onChange={(e) => seekToLap(Number(e.target.value))}
          data-testid="lap-scrubber"
          className="absolute inset-0 h-2 w-full cursor-pointer opacity-0 disabled:cursor-default"
        />
        <div
          className="pointer-events-none absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-white shadow"
          style={{ left: `calc(${(currentLap / distance) * 100}% - 4px)` }}
        />
      </div>
    </div>
  );
}
