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

export function usePanelHistory() {
  const lapRows = useRaceStore((s) => s.lapRows);
  const stintRows = useRaceStore((s) => s.stintRows);
  const gridDrivers = useRaceStore((s) => s.gridDrivers);
  const totalLaps = useRaceStore((s) => s.totalLaps) || 1;
  const currentLap = useRaceStore((s) => s.currentLap) || 1;
  const session = useRaceStore((s) => s.session);
  const mock = getRaceHistoryMock();
  const liveLaps = lapRecordsFromApi(lapRows);
  const liveStintsRaw = stintRecordsFromApi(stintRows);
  const derivedStints = stintsFromLapRecords(liveLaps);
  const liveStints = derivedStints.length ? derivedStints : liveStintsRaw;
  const hasApi = liveLaps.length > 0 || liveStints.length > 0;
  const useMock = !hasApi && !session;
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
