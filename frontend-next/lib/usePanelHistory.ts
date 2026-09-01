import { useEffect, useState } from "react";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { getRaceHistoryMock } from "@/lib/mockRaceHistory";
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
  const currentLap = useRaceStore((s) => s.currentLap) || 1;
  const [lap, setLapState] = useState(Math.max(1, currentLap));
  const [pinned, setPinned] = useState(false);

  useEffect(() => {
    if (!pinned) setLapState(Math.max(1, currentLap));
  }, [currentLap, pinned]);

  function setLap(next: number) {
    setPinned(true);
    setLapState(Math.max(1, next));
  }

  function follow() {
    setPinned(false);
    setLapState(Math.max(1, currentLap));
  }

  return { lap, setLap, pinned, follow, currentLap };
}

export function usePanelHistory() {
  const lapRows = useRaceStore((s) => s.lapRows);
  const stintRows = useRaceStore((s) => s.stintRows);
  const gridDrivers = useRaceStore((s) => s.gridDrivers);
  const totalLaps = useRaceStore((s) => s.totalLaps) || 1;
  const currentLap = useRaceStore((s) => s.currentLap) || 1;
  const session = useRaceStore((s) => s.session);
  const ready = useAnalyticsReady();
  const mock = getRaceHistoryMock();
  const liveLaps = lapRecordsFromApi(lapRows);
  const liveStintsRaw = stintRecordsFromApi(stintRows);
  const derivedStints = stintsFromLapRecords(liveLaps);
  const liveStints = derivedStints.length ? derivedStints : liveStintsRaw;
  const hasApi = liveLaps.length > 0 || liveStints.length > 0;
  const useMock = !hasApi && !session;
  if (!ready) {
    return {
      laps: [] as ReturnType<typeof lapRecordsFromApi>,
      stints: [] as ReturnType<typeof stintRecordsFromApi>,
      pitStops: [] as ReturnType<typeof pitStopsFromLaps>,
      drivers: gridDrivers.length ? gridDrivers : MOCK_DRIVERS_2025,
      fromApi: false,
      totalLaps,
      currentLap,
    };
  }
  const laps = hasApi ? lapsUpTo(liveLaps, currentLap) : useMock ? lapsUpTo(mock.laps, currentLap) : [];
  const stints = hasApi ? stintsUpTo(liveStints, currentLap) : useMock ? stintsUpTo(mock.stints, currentLap) : [];
  return {
    laps,
    stints,
    pitStops: hasApi
      ? pitStopsFromLaps(lapRows).filter((p) => p.lap <= currentLap)
      : useMock
        ? mock.pitStops.filter((p) => p.lap <= currentLap)
        : [],
    drivers: gridDrivers.length ? gridDrivers : MOCK_DRIVERS_2025,
    fromApi: hasApi,
    totalLaps,
    currentLap,
  };
}
