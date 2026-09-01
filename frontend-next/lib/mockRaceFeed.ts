import { MOCK_DRIVERS_2025, zandvoortOvalCoords } from "@/lib/mockData";
import { mockRecommendation } from "@/lib/api";
import { ghostCarFromTick, ghostPlaybackAt } from "@/lib/ghostCar";
import { annotateGhostTower } from "@/lib/mapCars";
import { buildPath, headingAtFraction, pointAtFraction } from "@/lib/trackGeometry";
import type { useRaceStore } from "@/store/raceStore";
import type { CarState, GhostTickData } from "@/lib/types";

type Store = typeof useRaceStore;

const TOTAL_LAPS = 72;
const LAP_TIME_S = 71.5;

interface DriverSim {
  code: string;
  baseFrac: number;
  paceOffset: number; // seconds/lap slower(+)/faster(-) than reference
  compound: CarState["compound"];
  tyreLifeStart: number;
  pitStops: number;
}

function buildDrivers(): DriverSim[] {
  const compounds: CarState["compound"][] = ["HARD", "MEDIUM", "SOFT"];
  return MOCK_DRIVERS_2025.map((d, i) => ({
    code: d.driver_code,
    baseFrac: -(i * (LAP_TIME_S / MOCK_DRIVERS_2025.length)) / LAP_TIME_S,
    paceOffset: (i * 0.06) + (Math.random() - 0.5) * 0.15,
    compound: compounds[i % compounds.length],
    tyreLifeStart: 2 + i,
    pitStops: i % 3 === 0 ? 1 : 0,
  }));
}

export class MockRaceFeed {
  private store: Store;
  private raf = 0;
  private interval: ReturnType<typeof setInterval> | null = null;
  private path = (() => {
    const coords = zandvoortOvalCoords();
    return buildPath(coords.x, coords.y);
  })();
  private drivers = buildDrivers();
  private elapsedRaceS = 0;
  private lastTickAt = 0;
  private commsTimer: ReturnType<typeof setInterval> | null = null;
  private recSent = false;

  constructor(store: Store) {
    this.store = store;
  }

  start() {
    this.lastTickAt = performance.now();
    this.elapsedRaceS = 0;
    const total = this.store.getState().session?.totalLaps || this.store.getState().totalLaps || TOTAL_LAPS;
    this.store.getState().setTotalLaps(total);
    this.store.getState().setCurrentLap(1);
    this.store.getState().setPlaybackSpeed(1);
    this.store.getState().setIsPlaying(this.store.getState().consolePlayState === "racing");
    this.interval = setInterval(() => this.tick(), 500);
    this.commsTimer = setInterval(() => this.maybeEmitComms(), 6000);
    this.tick();
  }

  stop() {
    if (this.interval) clearInterval(this.interval);
    if (this.commsTimer) clearInterval(this.commsTimer);
  }

  private speedMultiplier(): number {
    const { consoleMode, isPlaying, playbackSpeed } = this.store.getState();
    if (consoleMode === "live") return 1;
    return isPlaying ? playbackSpeed : 0;
  }

  private tick() {
    const now = performance.now();
    const seek = this.store.getState().seekLap;
    if (seek != null) {
      this.elapsedRaceS = Math.max(0, (seek - 1) * LAP_TIME_S);
      this.store.getState().clearSeekLap();
    }
    const dtS = ((now - this.lastTickAt) / 1000) * this.speedMultiplier();
    this.lastTickAt = now;
    if (this.store.getState().consolePlayState === "racing") this.elapsedRaceS += dtS;

    const totalLaps = this.store.getState().totalLaps || TOTAL_LAPS;

    const cars: Record<string, CarState> = {};
    const rows = this.drivers.map((d) => {
      const paceLapTime = LAP_TIME_S + d.paceOffset;
      const frac = d.baseFrac + this.elapsedRaceS / paceLapTime;
      const lapNumber = Math.floor(frac) + 1;
      return { d, frac, paceLapTime, lapNumber };
    });
    rows.sort((a, b) => b.frac - a.frac);

    rows.forEach((r, idx) => {
      const meta = MOCK_DRIVERS_2025.find((m) => m.driver_code === r.d.code)!;
      const point = pointAtFraction(this.path, r.frac);
      const heading = headingAtFraction(this.path, r.frac);
      const ahead = rows[idx - 1];
      const gapAheadS = ahead ? Math.max(0, (r.frac - ahead.frac) * -1 * r.paceLapTime) : null;
      cars[r.d.code] = {
        driver_code: r.d.code,
        driver_number: meta.driver_number,
        full_name: meta.full_name,
        team: meta.team,
        team_colour: meta.team_colour,
        position: idx + 1,
        lap_number: Math.min(r.lapNumber, totalLaps),
        compound: r.d.compound,
        tyre_life: r.d.tyreLifeStart + Math.floor(this.elapsedRaceS / paceOf(r.d)),
        gap_to_leader_s: idx === 0 ? 0 : (rows[0].frac - r.frac) * -1 * r.paceLapTime,
        gap_ahead_s: gapAheadS,
        gap_ahead_history: [gapAheadS ?? 0, gapAheadS ?? 0, gapAheadS ?? 0],
        last_lap_s: paceOf(r.d),
        pit_stops: r.d.pitStops,
        is_pitted: false,
        is_dnf: false,
        x: point.x,
        y: point.y,
        speed_kph: 200 + Math.sin(r.frac * Math.PI * 2) * 100 + 120,
        heading_rad: heading,
        laps_remaining: Math.max(0, totalLaps - r.lapNumber),
        total_laps: totalLaps,
        is_aris_driver: false,
      };
    });

    const { arisDriver, isARISOn, setCars, setGhostCar, setCurrentLap, setRacePhase } = this.store.getState();
    const focus = arisDriver ?? "VER";
    if (cars[focus]) cars[focus].is_aris_driver = true;
    setCars(cars);
    setCurrentLap(Math.min(rows[0]?.lapNumber ?? 1, totalLaps));
    const lap = rows[0]?.lapNumber ?? 1;
    setRacePhase(lap >= 12 && lap <= 15 ? "SC" : "GREEN");

    if (isARISOn && cars[focus]) {
      const real = cars[focus];
      const st = this.store.getState();
      const playback =
        st.ghostLapS.length > 1
          ? ghostPlaybackAt({
              elapsedS: st.replayElapsedS || this.elapsedRaceS,
              ghostLapS: st.ghostLapS,
              ghostCumulativeS: st.ghostCumulativeS,
              totalLaps,
              pitLaps: st.activeStrategy?.pit_laps ?? st.r2Ghost?.strategy.pit_laps ?? [],
              pitLossS: st.pitLossS,
              pitCompounds: st.activeStrategy?.pit_compounds ?? st.r2Ghost?.strategy.compounds,
            })
          : ghostPlaybackAt({
              elapsedS: this.elapsedRaceS,
              ghostLapS: Array.from({ length: totalLaps + 1 }, (_, i) => (i === 0 ? NaN : LAP_TIME_S)),
              ghostCumulativeS: Array.from({ length: totalLaps + 1 }, (_, i) => i * LAP_TIME_S),
              totalLaps,
              pitLaps: [],
              pitLossS: st.pitLossS,
            });
      const ghostPoint = pointAtFraction(this.path, playback.path_frac);
      const tick: GhostTickData = {
        driver_code: focus,
        divergence_lap: 1,
        aris_action: "STAY_OUT",
        real_action: "STAY_OUT",
        ghost_tyre: "HARD",
        ghost_tyre_age: real.tyre_life,
        ghost_position: Math.max(1, (real.position ?? 1) - 1),
        ghost_cumulative_delta: 0,
        active: true,
        outcome: null,
        delta_history: [],
        ghost_compound: "HARD",
        from_lap_one: true,
      };
      const car = annotateGhostTower(ghostCarFromTick(tick, real, lap, totalLaps, playback), cars, real);
      setGhostCar({
        ...car,
        x: ghostPoint.x,
        y: ghostPoint.y,
      });
    } else {
      setGhostCar(null);
    }

    if (isARISOn && !this.recSent && lap >= 23) {
      this.recSent = true;
      this.store.getState().setPendingRecommendation(mockRecommendation(lap));
      this.store.getState().pushComms({
        id: `comms-rec-${lap}`,
        lap,
        source: "ARIS",
        text: `Strategy call: Box this lap → HARD. Projected exit: P4 +2.1s ahead of car ahead. Confidence: 82% | Delta: -3.4s vs stay-out`,
        timestamp: Date.now(),
      });
    }
  }

  private maybeEmitComms() {
    const { isARISOn, currentLap, pushComms } = this.store.getState();
    if (!isARISOn) return;
    const lines = [
      "Gap to car ahead stable at 1.8s. Undercut window remains open.",
      "Tyre delta tracking G1.5 prior — HARD 0.03 s/lap.",
      "No SC risk detected in the next 3 laps.",
    ];
    pushComms({
      id: `comms-${Date.now()}`,
      lap: currentLap,
      source: "FIELD",
      text: lines[Math.floor(Math.random() * lines.length)],
      timestamp: Date.now(),
    });
  }
}

function paceOf(d: DriverSim): number {
  return LAP_TIME_S + d.paceOffset;
}
