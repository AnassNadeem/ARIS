import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import type {
  ARISRecommendation,
  CarState,
  CircuitCoords,
  CommsEntry,
  GhostTickData,
  PhaseHistoryEntry,
  RacePhase,
  SessionMeta,
  DriverListing,
  ApiLapRow,
  ApiStintRow,
  StratPlan,
} from "@/lib/types";

export type ARISMode = "assisted" | "auto";
export type ConsolePlayState = "ready" | "starting" | "racing";
export type ExplainSubTab = "deg" | "ghost" | "debrief";
export type ReplayPackStage = "empty" | "metadata" | "minimal" | "full";

export interface RaceStore {
  // Session
  session: SessionMeta | null;
  consoleMode: "replay" | "live";
  /** Replay/live start gate: header Start → track lights-out → racing. */
  consolePlayState: ConsolePlayState;
  packStage: ReplayPackStage;
  packProgress: number;
  packGpsReady: boolean;
  packToast: string | null;
  debriefDismissed: boolean;
  debriefOpen: boolean;
  isARISOn: boolean;
  arisEnabled: boolean;
  arisMode: ARISMode;
  arisModeLocked: boolean;
  arisDriver: string | null;
  selectedDriver: string | null;
  strategies: StratPlan[] | null;
  selectedStrategy: StratPlan | null;
  driverLocked: boolean;
  focusDriver: string | null;
  copilotDocked: boolean;

  // Live data — high frequency. Panels should subscribe with a selector so
  // only the slice that changed triggers a re-render.
  cars: Record<string, CarState>;
  ghostCar: CarState | null;
  /** Full ghost state from the backend tick — includes delta history and outcome. */
  ghostData: GhostTickData | null;
  /** Why `ghostData` is empty right now — lets the UI explain instead of going silent. */
  ghostReason: string | null;
  currentLap: number;
  totalLaps: number;
  racePhase: RacePhase;
  rainfall: boolean;
  raceFinished: boolean;

  // Playback (replay only)
  isPlaying: boolean;
  playbackSpeed: 1 | 2 | 4 | 8 | 16 | 25 | 50;
  scZones: { startLap: number; endLap: number; kind: "SC" | "VSC" | "RED_FLAG" }[];
  /** Full FSM phase history — used to render coloured bands on LapTimesChart. */
  phaseHistory: PhaseHistoryEntry[];

  // Connection
  connectionStatus: "disconnected" | "connecting" | "connected" | "reconnecting";
  connectionLagMs: number;

  gridDrivers: DriverListing[];
  lapRows: ApiLapRow[];
  stintRows: ApiStintRow[];
  waitingForRace: boolean;
  waitingMessage: string | null;
  circuitOutline: CircuitCoords | null;
  seekLap: number | null;

  // Comms
  commsLog: CommsEntry[];
  pendingRecommendation: ARISRecommendation | null;
  /** Last strategy used for the ghost after Auto-approve clears the pending card. */
  lastRecommendation: ARISRecommendation | null;
  copilotEnabled: boolean;
  strategyLoading: boolean;
  strategyEpoch: number;
  explainTabRequest: ExplainSubTab | null;

  // Actions
  setSession: (session: SessionMeta | null) => void;
  setConsoleMode: (mode: "replay" | "live") => void;
  setConsolePlayState: (state: ConsolePlayState) => void;
  beginLightsOut: () => void;
  startRacing: () => void;
  setPackStatus: (status: { stage: ReplayPackStage; progress?: number; gpsReady?: boolean }) => void;
  setPackToast: (message: string | null) => void;
  setDebriefDismissed: (on: boolean) => void;
  setDebriefOpen: (on: boolean) => void;
  setARISOn: (on: boolean) => void;
  setArisEnabled: (on: boolean) => void;
  setARISMode: (mode: ARISMode) => void;
  setARISModeLocked: (locked: boolean) => void;
  setARISDriver: (code: string | null) => void;
  setSelectedDriver: (code: string | null) => void;
  setDriverLocked: (locked: boolean) => void;
  setStrategies: (plans: StratPlan[] | null) => void;
  setSelectedStrategy: (plan: StratPlan | null) => void;
  setFocusDriver: (code: string | null) => void;
  setCopilotDocked: (on: boolean) => void;
  setCars: (cars: Record<string, CarState>) => void;
  upsertCar: (car: CarState) => void;
  setGhostCar: (car: CarState | null) => void;
  setGhostData: (data: GhostTickData | null) => void;
  setGhostReason: (reason: string | null) => void;
  setCurrentLap: (lap: number) => void;
  setTotalLaps: (laps: number) => void;
  setRacePhase: (phase: RacePhase) => void;
  setRainfall: (on: boolean) => void;
  setRaceFinished: (on: boolean) => void;
  setIsPlaying: (playing: boolean) => void;
  setPlaybackSpeed: (speed: 1 | 2 | 4 | 8 | 16 | 25 | 50) => void;
  pushPhaseHistory: (entry: PhaseHistoryEntry) => void;
  setConnectionStatus: (status: RaceStore["connectionStatus"], lagMs?: number) => void;
  setGridDrivers: (drivers: DriverListing[]) => void;
  setLapRows: (rows: ApiLapRow[]) => void;
  setStintRows: (rows: ApiStintRow[]) => void;
  setWaiting: (waiting: boolean, message?: string | null) => void;
  setCircuitOutline: (coords: CircuitCoords | null) => void;
  seekToLap: (lap: number) => void;
  clearSeekLap: () => void;
  pushComms: (entry: CommsEntry) => void;
  setPendingRecommendation: (rec: ARISRecommendation | null) => void;
  setCopilotEnabled: (on: boolean) => void;
  setStrategyLoading: (on: boolean) => void;
  requestStrategy: () => void;
  setExplainTabRequest: (tab: ExplainSubTab | null) => void;
  approveRecommendation: () => void;
  denyRecommendation: () => void;
  alterRecommendation: (changes: Partial<ARISRecommendation>) => void;
  reset: () => void;
}

const initialState = {
  session: null as SessionMeta | null,
  consoleMode: "replay" as const,
  consolePlayState: "ready" as ConsolePlayState,
  packStage: "empty" as ReplayPackStage,
  packProgress: 0,
  packGpsReady: false,
  packToast: null as string | null,
  debriefDismissed: false,
  debriefOpen: false,
  isARISOn: false,
  arisEnabled: false,
  arisMode: "auto" as ARISMode,
  arisModeLocked: false,
  arisDriver: null as string | null,
  selectedDriver: null as string | null,
  strategies: null as StratPlan[] | null,
  selectedStrategy: null as StratPlan | null,
  driverLocked: false,
  focusDriver: null as string | null,
  copilotDocked: false,
  cars: {} as Record<string, CarState>,
  ghostCar: null as CarState | null,
  ghostData: null as GhostTickData | null,
  ghostReason: null as string | null,
  currentLap: 1,
  totalLaps: 0,
  racePhase: "GREEN" as RacePhase,
  rainfall: false,
  raceFinished: false,
  isPlaying: false,
  playbackSpeed: 1 as const,
  scZones: [] as { startLap: number; endLap: number; kind: "SC" | "VSC" | "RED_FLAG" }[],
  phaseHistory: [] as PhaseHistoryEntry[],
  connectionStatus: "disconnected" as const,
  connectionLagMs: 0,
  gridDrivers: [] as DriverListing[],
  lapRows: [] as ApiLapRow[],
  stintRows: [] as ApiStintRow[],
  waitingForRace: false,
  waitingMessage: null as string | null,
  circuitOutline: null as CircuitCoords | null,
  seekLap: null as number | null,
  commsLog: [] as CommsEntry[],
  pendingRecommendation: null as ARISRecommendation | null,
  lastRecommendation: null as ARISRecommendation | null,
  copilotEnabled: true,
  strategyLoading: false,
  strategyEpoch: 0,
  explainTabRequest: null as ExplainSubTab | null,
};

export const useRaceStore = create<RaceStore>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    setSession: (session) =>
      set({
        session,
        currentLap: 1,
        totalLaps: session?.totalLaps && session.totalLaps > 0 ? session.totalLaps : 0,
        isPlaying: false,
        consolePlayState: "ready",
        packStage: "empty",
        packProgress: 0,
        packGpsReady: false,
        packToast: null,
        debriefDismissed: false,
        debriefOpen: false,
        playbackSpeed: 1,
        cars: {},
        ghostCar: null,
        ghostData: null,
        ghostReason: null,
        circuitOutline: null,
        seekLap: null,
        waitingForRace: false,
        waitingMessage: null,
        lapRows: [],
        stintRows: [],
        commsLog: [],
        phaseHistory: [],
        rainfall: false,
        raceFinished: false,
        arisModeLocked: false,
        pendingRecommendation: null,
        lastRecommendation: null,
        strategyLoading: false,
      }),
    setConsoleMode: (consoleMode) => set({ consoleMode }),
    setConsolePlayState: (consolePlayState) => set({ consolePlayState }),
    beginLightsOut: () => set({ consolePlayState: "starting" }),
    startRacing: () => set({ consolePlayState: "racing", isPlaying: true }),
    setPackStatus: ({ stage, progress, gpsReady }) => {
      const cur = get();
      if (
        cur.packStage === stage &&
        (progress == null || cur.packProgress === progress) &&
        (gpsReady == null || cur.packGpsReady === gpsReady)
      ) {
        return;
      }
      set({
        packStage: stage,
        packProgress: progress ?? cur.packProgress,
        packGpsReady: gpsReady ?? cur.packGpsReady,
      });
    },
    setPackToast: (packToast) => set({ packToast }),
    setDebriefDismissed: (debriefDismissed) => set({ debriefDismissed }),
    setDebriefOpen: (debriefOpen) => set({ debriefOpen }),
    setARISOn: (isARISOn) =>
      set(
        isARISOn
          ? { isARISOn, arisEnabled: true }
          : {
              isARISOn,
              arisEnabled: false,
              strategies: null,
              selectedStrategy: null,
              driverLocked: false,
            },
      ),
    setArisEnabled: (arisEnabled) => get().setARISOn(arisEnabled),
    setARISMode: (arisMode) => {
      if (get().arisModeLocked) return;
      set({ arisMode });
    },
    setARISModeLocked: (arisModeLocked) => set({ arisModeLocked }),
    setARISDriver: (arisDriver) =>
      set({ arisDriver, selectedDriver: arisDriver, focusDriver: arisDriver ?? get().focusDriver }),
    setSelectedDriver: (selectedDriver) =>
      set({
        selectedDriver,
        arisDriver: selectedDriver,
        focusDriver: selectedDriver ?? get().focusDriver,
        driverLocked: false,
        strategies: null,
        selectedStrategy: null,
      }),
    setDriverLocked: (driverLocked) => set({ driverLocked }),
    setStrategies: (strategies) => set({ strategies }),
    setSelectedStrategy: (selectedStrategy) => set({ selectedStrategy }),
    setFocusDriver: (focusDriver) => set({ focusDriver }),
    setCopilotDocked: (copilotDocked) => set({ copilotDocked }),
    setCars: (cars) => {
      const prev = get().cars;
      if (prev === cars) return;
      const nextKeys = Object.keys(cars);
      const prevKeys = Object.keys(prev);
      if (prevKeys.length === nextKeys.length && nextKeys.every((k) => prev[k] === cars[k])) return;
      set({ cars });
    },
    upsertCar: (car) =>
      set((s) => ({ cars: { ...s.cars, [car.driver_code]: car } })),
    setGhostCar: (ghostCar) => set({ ghostCar }),
    setGhostData: (ghostData) => set({ ghostData }),
    setGhostReason: (ghostReason) => set({ ghostReason }),
    setCurrentLap: (currentLap) => {
      if (get().currentLap === currentLap) return;
      set({ currentLap });
    },
    setTotalLaps: (totalLaps) => {
      if (get().totalLaps === totalLaps) return;
      set({ totalLaps });
    },
    setRacePhase: (racePhase) => {
      if (get().racePhase === racePhase) return;
      set({ racePhase });
    },
    setRainfall: (rainfall) => {
      if (get().rainfall === rainfall) return;
      set({ rainfall });
    },
    setRaceFinished: (raceFinished) => {
      if (get().raceFinished === raceFinished) return;
      set({ raceFinished, isPlaying: raceFinished ? false : get().isPlaying });
    },
    setIsPlaying: (isPlaying) => set({ isPlaying }),
    setPlaybackSpeed: (playbackSpeed) => set({ playbackSpeed }),
    pushPhaseHistory: (entry) =>
      set((s) => ({ phaseHistory: [...s.phaseHistory, entry] })),
    setConnectionStatus: (connectionStatus, lagMs) => {
      const nextLag = lagMs ?? get().connectionLagMs;
      if (get().connectionStatus === connectionStatus && get().connectionLagMs === nextLag) return;
      set({ connectionStatus, connectionLagMs: nextLag });
    },
    setGridDrivers: (gridDrivers) => set({ gridDrivers }),
    setLapRows: (lapRows) => {
      if (lapRows === get().lapRows) return;
      if (lapRows.length === get().lapRows.length && lapRows.length > 0) {
        const a = lapRows[lapRows.length - 1];
        const b = get().lapRows[get().lapRows.length - 1];
        if (
          a.driver_code === b.driver_code &&
          a.lap_number === b.lap_number &&
          a.lap_time_ms === b.lap_time_ms &&
          a.end_time_ms === b.end_time_ms
        ) {
          return;
        }
      }
      set({ lapRows });
    },
    setStintRows: (stintRows) => {
      if (stintRows === get().stintRows) return;
      if (stintRows.length === get().stintRows.length && stintRows.length > 0) {
        const a = stintRows[stintRows.length - 1];
        const b = get().stintRows[get().stintRows.length - 1];
        if (a.driver_code === b.driver_code && a.lap_end === b.lap_end && a.compound === b.compound) return;
      }
      set({ stintRows });
    },
    setWaiting: (waitingForRace, waitingMessage = null) => set({ waitingForRace, waitingMessage }),
    setCircuitOutline: (circuitOutline) => set({ circuitOutline }),
    seekToLap: (lap) => set({ currentLap: lap, seekLap: lap }),
    clearSeekLap: () => set({ seekLap: null }),
    pushComms: (entry) =>
      set((s) => {
        if (s.commsLog.some((c) => c.id === entry.id)) return s;
        return { commsLog: [...s.commsLog, entry] };
      }),
    setPendingRecommendation: (pendingRecommendation) =>
      set(
        pendingRecommendation
          ? { pendingRecommendation, lastRecommendation: pendingRecommendation }
          : { pendingRecommendation },
      ),
    setCopilotEnabled: (copilotEnabled) => set({ copilotEnabled }),
    setStrategyLoading: (strategyLoading) => set({ strategyLoading }),
    requestStrategy: () =>
      set((s) => ({
        strategyEpoch: s.strategyEpoch + 1,
        pendingRecommendation: null,
        strategyLoading: true,
      })),
    setExplainTabRequest: (explainTabRequest) => set({ explainTabRequest }),

    approveRecommendation: () => {
      const rec = get().pendingRecommendation;
      if (!rec) return;
      set((s) => ({
        pendingRecommendation: null,
        commsLog: [
          ...s.commsLog,
          {
            id: `${rec.id}-approved-${Date.now()}`,
            lap: rec.lap,
            source: "ARIS",
            text: `Approved: ${rec.label}. Ghost driver executing strategy.`,
            timestamp: Date.now(),
          },
        ],
      }));
    },

    denyRecommendation: () => {
      const rec = get().pendingRecommendation;
      if (!rec) return;
      set((s) => ({
        pendingRecommendation: null,
        commsLog: [
          ...s.commsLog,
          {
            id: `${rec.id}-denied-${Date.now()}`,
            lap: rec.lap,
            source: "ARIS",
            text: `Denied: ${rec.label}. Recalculating Plan B. Ghost stays out.`,
            timestamp: Date.now(),
          },
        ],
      }));
    },

    alterRecommendation: (changes) => {
      const rec = get().pendingRecommendation;
      if (!rec) return;
      const altered = { ...rec, ...changes };
      set((s) => ({
        pendingRecommendation: null,
        commsLog: [
          ...s.commsLog,
          {
            id: `${rec.id}-altered-${Date.now()}`,
            lap: rec.lap,
            source: "ARIS",
            text: `Altered: now targeting ${altered.action.pit_compound ?? rec.action.pit_compound} on lap ${
              altered.action.pit_lap ?? rec.action.pit_lap
            }.`,
            timestamp: Date.now(),
          },
        ],
      }));
    },

    reset: () => set({ ...initialState }),
  })),
);
