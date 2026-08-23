import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import type {
  ARISRecommendation,
  CarState,
  CommsEntry,
  RacePhase,
  SessionMeta,
} from "@/lib/types";

export type ARISMode = "assisted" | "auto";

export interface RaceStore {
  // Session
  session: SessionMeta | null;
  consoleMode: "replay" | "live";
  isARISOn: boolean;
  arisMode: ARISMode;
  arisDriver: string | null;

  // Live data — high frequency. Panels should subscribe with a selector so
  // only the slice that changed triggers a re-render.
  cars: Record<string, CarState>;
  ghostCar: CarState | null;
  currentLap: number;
  totalLaps: number;
  racePhase: RacePhase;

  // Playback (replay only)
  isPlaying: boolean;
  playbackSpeed: 1 | 2 | 4 | 8 | 16 | 25 | 50;
  scZones: { startLap: number; endLap: number; kind: "SC" | "VSC" | "RED" }[];

  // Connection
  connectionStatus: "disconnected" | "connecting" | "connected" | "reconnecting";
  connectionLagMs: number;

  // Comms
  commsLog: CommsEntry[];
  pendingRecommendation: ARISRecommendation | null;

  // Actions
  setSession: (session: SessionMeta | null) => void;
  setConsoleMode: (mode: "replay" | "live") => void;
  setARISOn: (on: boolean) => void;
  setARISMode: (mode: ARISMode) => void;
  setARISDriver: (code: string | null) => void;
  setCars: (cars: Record<string, CarState>) => void;
  upsertCar: (car: CarState) => void;
  setGhostCar: (car: CarState | null) => void;
  setCurrentLap: (lap: number) => void;
  setTotalLaps: (laps: number) => void;
  setRacePhase: (phase: RacePhase) => void;
  setIsPlaying: (playing: boolean) => void;
  setPlaybackSpeed: (speed: 1 | 2 | 4 | 8 | 16 | 25 | 50) => void;
  setConnectionStatus: (status: RaceStore["connectionStatus"], lagMs?: number) => void;
  pushComms: (entry: CommsEntry) => void;
  setPendingRecommendation: (rec: ARISRecommendation | null) => void;
  approveRecommendation: () => void;
  denyRecommendation: () => void;
  alterRecommendation: (changes: Partial<ARISRecommendation>) => void;
  reset: () => void;
}

const initialState = {
  session: null as SessionMeta | null,
  consoleMode: "replay" as const,
  isARISOn: false,
  arisMode: "assisted" as ARISMode,
  arisDriver: null as string | null,
  cars: {} as Record<string, CarState>,
  ghostCar: null as CarState | null,
  currentLap: 1,
  totalLaps: 72,
  racePhase: "GREEN" as RacePhase,
  isPlaying: false,
  playbackSpeed: 4 as const,
  scZones: [] as { startLap: number; endLap: number; kind: "SC" | "VSC" | "RED" }[],
  connectionStatus: "disconnected" as const,
  connectionLagMs: 0,
  commsLog: [] as CommsEntry[],
  pendingRecommendation: null as ARISRecommendation | null,
};

export const useRaceStore = create<RaceStore>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    setSession: (session) => set({ session }),
    setConsoleMode: (consoleMode) => set({ consoleMode }),
    setARISOn: (isARISOn) => set({ isARISOn }),
    setARISMode: (arisMode) => set({ arisMode }),
    setARISDriver: (arisDriver) => set({ arisDriver }),
    setCars: (cars) => set({ cars }),
    upsertCar: (car) =>
      set((s) => ({ cars: { ...s.cars, [car.driver_code]: car } })),
    setGhostCar: (ghostCar) => set({ ghostCar }),
    setCurrentLap: (currentLap) => set({ currentLap }),
    setTotalLaps: (totalLaps) => set({ totalLaps }),
    setRacePhase: (racePhase) => set({ racePhase }),
    setIsPlaying: (isPlaying) => set({ isPlaying }),
    setPlaybackSpeed: (playbackSpeed) => set({ playbackSpeed }),
    setConnectionStatus: (connectionStatus, lagMs) =>
      set({ connectionStatus, connectionLagMs: lagMs ?? get().connectionLagMs }),
    pushComms: (entry) => set((s) => ({ commsLog: [...s.commsLog, entry] })),
    setPendingRecommendation: (pendingRecommendation) => set({ pendingRecommendation }),

    approveRecommendation: () => {
      const rec = get().pendingRecommendation;
      if (!rec) return;
      set((s) => ({
        pendingRecommendation: null,
        commsLog: [
          ...s.commsLog,
          {
            id: `${rec.id}-approved`,
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
            id: `${rec.id}-denied`,
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
            id: `${rec.id}-altered`,
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
