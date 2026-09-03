import { useEffect, useState } from "react";
import {
  lapRecordsFromApi,
  lapsUpTo,
  pitStopsFromLaps,
  stintRecordsFromApi,
  stintsFromLapRecords,
  stintsUpTo,
} from "@/lib/panelData";
import { useRaceStore } from "@/store/raceStore";

/** Lap-data analytics stay empty until lights-out. Live calls startRacing() when cars arrive. */
export function useAnalyticsReady(): boolean {
  return useRaceStore((s) => s.consolePlayState === "racing");
}

/**
 * Chart lap that tracks the race clock until the user edits the input (pin).
 * Call `follow()` to unpin and resume auto-advance.
 */
export function useFollowRaceLap() {
  const currentLap = useRaceStore((s) => s.currentLap) || 0;
  const [lap, setLapState] = useState(Math.max(0, currentLap));
  const [pinned, setPinned] = useState(false);

  useEffect(() => {
    if (!pinned) setLapState(Math.max(0, currentLap));
  }, [currentLap, pinned]);

  function setLap(next: number) {
    setPinned(true);
    setLapState(Math.max(0, next));
  }

  function follow() {
    setPinned(false);
    setLapState(Math.max(0, currentLap));
  }

  return { lap, setLap, pinned, follow, currentLap };
}

export function usePanelHistory() {
  const lapRows = useRaceStore((s) => s.lapRows);
  const stintRows = useRaceStore((s) => s.stintRows);
  const gridDrivers = useRaceStore((s) => s.gridDrivers);
  const totalLaps = useRaceStore((s) => s.totalLaps) || 1;
  const currentLap = useRaceStore((s) => s.currentLap) || 0;
  const ready = useAnalyticsReady();
  const liveLaps = lapRecordsFromApi(lapRows);
  const liveStintsRaw = stintRecordsFromApi(stintRows);
  const derivedStints = stintsFromLapRecords(liveLaps);
  const liveStints = derivedStints.length ? derivedStints : liveStintsRaw;
  const hasApi = liveLaps.length > 0 || liveStints.length > 0;
  if (!ready) {
    return {
      laps: [] as ReturnType<typeof lapRecordsFromApi>,
      stints: [] as ReturnType<typeof stintRecordsFromApi>,
      pitStops: [] as ReturnType<typeof pitStopsFromLaps>,
      drivers: gridDrivers,
      fromApi: false,
      totalLaps,
      currentLap,
    };
  }
  const laps = hasApi ? lapsUpTo(liveLaps, currentLap) : [];
  const stints = hasApi ? stintsUpTo(liveStints, currentLap) : [];
  return {
    laps,
    stints,
    pitStops: hasApi ? pitStopsFromLaps(lapRows).filter((p) => p.lap <= currentLap) : [],
    drivers: gridDrivers,
    fromApi: hasApi,
    totalLaps,
    currentLap,
  };
}
