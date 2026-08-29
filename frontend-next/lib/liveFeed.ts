import { useRaceStore, type ReplayPackStage } from "@/store/raceStore";
import { circuitCoordsFromReplayOutline } from "@/lib/api";
import { isFullCircuitOutline } from "@/lib/circuitCache";
import { mapTimingAndPositions, mergeByDriverCode, mergeCars, sessionFlagToPhase, timingFingerprint } from "@/lib/mapCars";
import { asGhostTick, ghostCarFromTick, syntheticGhostCar, syntheticGhostTick } from "@/lib/ghostCar";
import type { ApiLapRow, ApiStintRow, CircuitCoords, LivePosition, LiveTimingRow } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

function setFeedStatus(status: "connecting" | "connected" | "disconnected" | "reconnecting", lagMs?: number) {
  useRaceStore.getState().setConnectionStatus(status, lagMs);
}

type SsePayload = {
  status?: {
    is_live?: boolean;
    current_lap?: number | null;
    total_laps?: number | null;
    session_flag?: string | null;
    session_ended?: boolean;
    year?: number | null;
    round_number?: number | null;
  };
  timing?: {
    rows?: LiveTimingRow[];
    current_lap?: number | null;
    is_live?: boolean;
    session_flag?: string | null;
    rainfall?: boolean;
  };
  weather?: { rainfall?: boolean | null };
  ghost?: unknown;
  ghost_reason?: string | null;
  is_delta?: boolean;
  positions?: {
    positions?: LivePosition[];
    is_live?: boolean;
    circuit_path?: { x: number[]; y: number[] } | null;
    markers?: CircuitCoords["markers"];
    pit_lane_x?: number[];
    pit_lane_y?: number[];
  };
  circuit_path?: { x: number[]; y: number[] } | null;
  markers?: CircuitCoords["markers"];
  pit_lane_x?: number[];
  pit_lane_y?: number[];
};

function applyPackStatus(st: {
  stage?: string;
  progress?: number;
  ready?: boolean;
  status?: string;
  flags?: { gps_ready?: boolean };
  gps_ready?: boolean;
}): ReplayPackStage {
  const store = useRaceStore.getState();
  const stage: ReplayPackStage =
    st.stage === "full" || st.stage === "minimal" || st.stage === "metadata" || st.stage === "empty"
      ? st.stage
      : st.ready || st.status === "ready"
        ? "minimal"
        : "metadata";
  const gpsReady = Boolean(st.flags?.gps_ready ?? st.gps_ready);
  const wasFull = store.packStage === "full";
  store.setPackStatus({ stage, progress: st.progress, gpsReady });
  if (stage === "full" && !wasFull) {
    store.setPackToast("Data fully loaded");
  }
  return stage;
}

function wantRefresh(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return new URLSearchParams(window.location.search).get("refresh") === "1";
  } catch {
    return false;
  }
}

function applyGhost(payload: SsePayload) {
  const store = useRaceStore.getState();
  if (!store.isARISOn) {
    if (store.ghostCar || store.ghostData || store.ghostReason !== "aris_disabled") {
      store.setGhostCar(null);
      store.setGhostData(null);
      store.setGhostReason("aris_disabled");
    }
    return;
  }
  const driver = store.arisDriver ?? store.session?.driverCode ?? store.focusDriver ?? null;
  const real = driver ? store.cars[driver] ?? null : null;
  const raw = payload.ghost;
  const patched =
    raw && typeof raw === "object" && driver && !(raw as { driver_code?: string }).driver_code
      ? { ...(raw as Record<string, unknown>), driver_code: driver }
      : raw;
  const tick = asGhostTick(patched);
  if (tick) {
    store.setGhostData(tick);
    store.setGhostCar(ghostCarFromTick(tick, real, store.currentLap, store.totalLaps));
    store.setGhostReason(null);
    return;
  }
  const rec = store.pendingRecommendation ?? store.lastRecommendation;
  if (rec && real && driver) {
    // fix-pass item 8: synthetic map-dot AND GhostDelta must agree. Derive a
    // one-point delta history from the recommendation so the panel isn't empty
    // while a ghost car is visible on the map.
    store.setGhostCar(syntheticGhostCar(rec, real, store.currentLap, store.totalLaps));
    store.setGhostData(syntheticGhostTick(rec, driver, store.currentLap));
    store.setGhostReason(null);
    return;
  }
  store.setGhostCar(null);
  store.setGhostData(null);
  store.setGhostReason(payload.ghost_reason ?? (driver ? "no_divergence" : "no_driver_selected"));
}

function applyCircuitPath(payload: SsePayload) {
  const coords = circuitCoordsFromReplayOutline({
    circuit_path: payload.circuit_path ?? payload.positions?.circuit_path,
    markers: payload.markers ?? payload.positions?.markers,
    pit_lane_x: payload.pit_lane_x ?? payload.positions?.pit_lane_x,
    pit_lane_y: payload.pit_lane_y ?? payload.positions?.pit_lane_y,
  });
  if (!coords || !isFullCircuitOutline(coords)) return;
  const store = useRaceStore.getState();
  const cur = store.circuitOutline;
  if (cur && cur.x.length >= coords.x.length) return;
  store.setCircuitOutline({ ...coords, available: true });
}

export class LiveSseFeed {
  private es: EventSource | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private lapsTimer: ReturnType<typeof setInterval> | null = null;
  private closed = false;
  private opened = false;
  private lastFp = "";
  onOpen?: () => void;
  onFailure?: () => void;

  connect() {
    this.closed = false;
    setFeedStatus("connecting");
    try {
      this.es = new EventSource(`${API_BASE}/api/live/stream`);
    } catch {
      this.startPoll();
      return;
    }
    this.es.onopen = () => {
      this.opened = true;
      setFeedStatus("connected", 0);
      this.onOpen?.();
    };
    this.es.onmessage = (ev) => {
      try {
        this.applyPayload(JSON.parse(ev.data) as SsePayload);
      } catch {
        /* ignore malformed frames */
      }
    };
    this.es.onerror = () => {
      setFeedStatus("disconnected");
      this.es?.close();
      this.es = null;
      this.startPoll();
    };
    this.lapsTimer = setInterval(() => void this.pollLapsAndStints(), 5000);
    void this.pollLapsAndStints();
  }

  private applyPayload(payload: SsePayload) {
    const store = useRaceStore.getState();
    const status = payload.status;
    const timingRows = payload.timing?.rows ?? [];
    const positions = payload.positions?.positions ?? [];
    const lap = status?.current_lap ?? payload.timing?.current_lap;
    const total = status?.total_laps;
    if (lap) store.setCurrentLap(lap);
    if (total) store.setTotalLaps(total);
    if (status?.session_flag) store.setRacePhase(sessionFlagToPhase(status.session_flag));
    else if (payload.timing?.session_flag) store.setRacePhase(sessionFlagToPhase(payload.timing.session_flag));
    if (status?.session_ended) store.setRaceFinished(true);
    const raining = payload.weather?.rainfall ?? payload.timing?.rainfall;
    if (typeof raining === "boolean") store.setRainfall(raining);
    applyCircuitPath(payload);
    const cars = mapTimingAndPositions(timingRows, positions, store.gridDrivers, total || store.totalLaps || 1, lap || 1);
    const fp = timingFingerprint(timingRows, positions);
    if (fp !== this.lastFp && Object.keys(cars).length) {
      this.lastFp = fp;
      const merged = mergeCars(store.cars, cars);
      if (merged !== store.cars) store.setCars(merged);
    }
    applyGhost(payload);
    setFeedStatus("connected", 0);
    if ((status?.is_live || payload.timing?.is_live) && !this.opened) {
      this.opened = true;
      this.onOpen?.();
    }
  }

  private startPoll() {
    if (this.pollTimer || this.closed) return;
    this.onFailure?.();
    const tick = async () => {
      try {
        const [status, timing, positions] = await Promise.all([
          fetchJson(`${API_BASE}/api/live/status`),
          fetchJson(`${API_BASE}/api/live/timing`),
          fetchJson(`${API_BASE}/api/live/positions`),
        ]);
        this.applyPayload({ status, timing, positions });
      } catch {
        setFeedStatus("reconnecting");
      }
    };
    void tick();
    this.pollTimer = setInterval(() => void tick(), 2000);
    if (!this.lapsTimer) {
      this.lapsTimer = setInterval(() => void this.pollLapsAndStints(), 5000);
    }
  }

  private async pollLapsAndStints() {
    try {
      const [laps, stints] = await Promise.all([
        fetchJson(`${API_BASE}/api/live/laps`),
        fetchJson(`${API_BASE}/api/live/stints`),
      ]);
      const store = useRaceStore.getState();
      if (Array.isArray(laps?.laps)) store.setLapRows(laps.laps as ApiLapRow[]);
      if (Array.isArray(stints?.stints)) store.setStintRows(stints.stints as ApiStintRow[]);
      if (laps?.current_lap) store.setCurrentLap(laps.current_lap);
    } catch {
      /* keep last-known laps */
    }
  }

  disconnect() {
    this.closed = true;
    this.es?.close();
    this.es = null;
    if (this.pollTimer) clearInterval(this.pollTimer);
    if (this.lapsTimer) clearInterval(this.lapsTimer);
    this.pollTimer = null;
    this.lapsTimer = null;
  }
}

const LOOKAHEAD_S = 30;

export class ReplayFrameFeed {
  private timer: ReturnType<typeof setInterval> | null = null;
  private sessionKey: number | null = null;
  private dateStart: Date | null = null;
  private dateEnd: Date | null = null;
  private greenFlagS = 0;
  private durationS = 0;
  private year = 0;
  private round = 0;
  private sessionType = "R";
  private elapsedS = 0;
  private lastWall = 0;
  private lastFp = "";
  private inFlight = false;
  private lastLapsAt = 0;
  private closed = false;
  private refreshOnce = false;
  private lastPrefetchAt = 0;
  private pollDurations: number[] = [];
  private lastTimingRows: LiveTimingRow[] = [];
  private lastPositions: LivePosition[] = [];
  private lastFrameAsOf: string | null = null;
  onOpen?: () => void;
  onFailure?: () => void;

  async connect(year: number, round: number, sessionType: string) {
    const store = useRaceStore.getState();
    setFeedStatus("connecting");
    store.setCurrentLap(1);
    store.setPlaybackSpeed(1);
    store.setIsPlaying(false);
    store.setCars({});
    store.setLapRows([]);
    store.setStintRows([]);
    store.setWaiting(true, "Loading session data…");
    this.year = year;
    this.round = round;
    this.sessionType = sessionType;
    this.elapsedS = 0;
    this.lastFp = "";
    this.inFlight = false;
    this.lastLapsAt = 0;
    this.lastPrefetchAt = 0;
    this.lastTimingRows = [];
    this.lastPositions = [];
    this.lastFrameAsOf = null;
    this.closed = false;
    this.refreshOnce = wantRefresh();
    if (this.refreshOnce) console.info("[ARIS] replay force refresh=1 — bypassing FastF1 caches");
    try {
      const meta = await fetchJson(
        `${API_BASE}/api/live/session-key?year=${year}&round_number=${round}&session_type=${sessionType}${this.refreshOnce ? "&refresh=1" : ""}`,
        15000,
      );
      if (!meta?.session_key) {
        setFeedStatus("disconnected");
        this.onFailure?.();
        return;
      }
      if (this.closed) return;
      this.sessionKey = Number(meta.session_key);
      this.dateStart = meta.date_start ? new Date(meta.date_start) : new Date();
      this.dateEnd = meta.date_end ? new Date(meta.date_end) : null;
      this.greenFlagS = Number(meta.green_flag_s || 0);
      this.elapsedS = 0;
      this.lastWall = performance.now();
      this.onOpen?.();
      void this.loadHistory(year, round, sessionType);
      const packOk = await this.waitForPack();
      if (this.closed) return;
      if (!packOk) {
        store.setWaiting(true, "Couldn't load session data. Try another session or refresh.");
        setFeedStatus("disconnected");
        this.onFailure?.();
        return;
      }
      this.refreshOnce = false;
      void this.warmLookahead();
      this.timer = setInterval(() => void this.tick(), 250);
      await this.tick();
    } catch {
      setFeedStatus("disconnected");
      this.onFailure?.();
    }
  }

  /**
   * Poll pack-status until stage >= minimal (Start can enable). Then keep
   * polling in the background until full GPS.
   */
  private async waitForPack(): Promise<boolean> {
    if (this.sessionKey == null) return false;
    const deadline = Date.now() + 5 * 60 * 1000;
    let nulls = 0;
    while (!this.closed && Date.now() < deadline) {
      const qs = new URLSearchParams({
        session_key: String(this.sessionKey),
        year: String(this.year),
        round_number: String(this.round),
        session_type: this.sessionType,
      });
      if (!useRaceStore.getState().circuitOutline?.x?.length) qs.set("outline", "1");
      const st = await fetchJson(`${API_BASE}/api/replay/pack-status?${qs}`, 8000);
      if (st) {
        nulls = 0;
        if (st.date_start) this.dateStart = new Date(st.date_start);
        if (st.date_end) this.dateEnd = new Date(st.date_end);
        if (st.green_flag_s) this.greenFlagS = Number(st.green_flag_s);
        const stage = applyPackStatus(st);
        applyCircuitPath(st);
        if (st.status === "error") {
          useRaceStore.getState().setWaiting(true, st.error || "Couldn't load session data.");
          return false;
        }
        if (stage === "minimal" || stage === "full" || st.status === "ready" || st.ready === true) {
          if (stage !== "full") this.watchPackUntilFull();
          return true;
        }
        const elapsed = typeof st.elapsed_s === "number" ? Math.round(st.elapsed_s) : null;
        const label =
          stage === "metadata"
            ? "Loading session metadata…"
            : "Preparing race data (laps, map)…";
        useRaceStore
          .getState()
          .setWaiting(true, elapsed != null ? `${label} ${elapsed}s` : label);
      } else {
        nulls += 1;
        if (nulls >= 3) {
          const liveQs = new URLSearchParams({
            session_key: String(this.sessionKey),
            year: String(this.year),
            round_number: String(this.round),
            session_type: this.sessionType,
          });
          if (!useRaceStore.getState().circuitOutline?.x?.length) liveQs.set("outline", "1");
          const fallback = await fetchJson(`${API_BASE}/api/live/replay-pack-status?${liveQs}`, 8000);
          if (fallback) {
            applyPackStatus(fallback);
            applyCircuitPath(fallback);
            if (fallback.status === "ready" || fallback.ready === true) return true;
          }
          const readyQs = new URLSearchParams({
            session_key: String(this.sessionKey),
            year: String(this.year),
            round_number: String(this.round),
          });
          const driver = useRaceStore.getState().arisDriver ?? useRaceStore.getState().focusDriver;
          if (driver) readyQs.set("driver", driver);
          const ready = await fetchJson(`${API_BASE}/api/live/replay-ready?${readyQs}`, 180000);
          if (ready?.green_flag_s) this.greenFlagS = Number(ready.green_flag_s);
          if (ready?.date_start) this.dateStart = new Date(ready.date_start);
          if (ready?.date_end) this.dateEnd = new Date(ready.date_end);
          return Boolean(ready?.ready);
        }
      }
      await sleep(1000);
    }
    return false;
  }

  private watchPackUntilFull() {
    if (this.sessionKey == null) return;
    const key = this.sessionKey;
    const year = this.year;
    const round = this.round;
    const sessionType = this.sessionType;
    const tick = async () => {
      if (this.closed) return;
      const qs = new URLSearchParams({
        session_key: String(key),
        year: String(year),
        round_number: String(round),
        session_type: sessionType,
      });
      if (!useRaceStore.getState().circuitOutline?.x?.length) qs.set("outline", "1");
      const st = await fetchJson(`${API_BASE}/api/replay/pack-status?${qs}`, 8000);
      if (this.closed) return;
      if (st) {
        const stage = applyPackStatus(st);
        applyCircuitPath(st);
        if (stage === "full") return;
      }
      window.setTimeout(() => void tick(), 2000);
    };
    void tick();
  }

  private async loadHistory(year: number, round: number, sessionType: string) {
    try {
      const [laps, stints] = await Promise.all([
        fetchJson(`${API_BASE}/api/session/${year}/${round}/${sessionType}/laps`, 20000),
        fetchJson(`${API_BASE}/api/session/${year}/${round}/${sessionType}/stints`, 20000),
      ]);
      if (this.closed) return;
      const store = useRaceStore.getState();
      if (Array.isArray(laps?.laps) && laps.laps.length) store.setLapRows(laps.laps as ApiLapRow[]);
      if (Array.isArray(stints?.stints) && stints.stints.length) store.setStintRows(stints.stints as ApiStintRow[]);
    } catch {
      /* pack laps via replay-frame as_of still fill the charts */
    }
  }

  private lapToElapsed(lap: number): number {
    const total = Math.max(1, useRaceStore.getState().totalLaps || 1);
    if (this.durationS > 0) return Math.max(0, ((lap - 1) / total) * this.durationS);
    return Math.max(0, (lap - 1) * 90);
  }

  private async pollReplayLaps(asOf: Date) {
    if (this.closed || this.sessionKey == null) return;
    const qs = `replay_session_key=${this.sessionKey}&as_of=${encodeURIComponent(asOf.toISOString())}`;
    try {
      const [laps, stints] = await Promise.all([
        fetchJson(`${API_BASE}/api/live/laps?${qs}`, 8000),
        fetchJson(`${API_BASE}/api/live/stints?${qs}`, 8000),
      ]);
      if (this.closed) return;
      const store = useRaceStore.getState();
      if (Array.isArray(laps?.laps) && laps.laps.length && store.lapRows.length === 0) {
        store.setLapRows(laps.laps as ApiLapRow[]);
      } else if (Array.isArray(laps?.laps) && laps.laps.length && store.lapRows.length < laps.laps.length) {
        store.setLapRows(laps.laps as ApiLapRow[]);
      }
      if (Array.isArray(stints?.stints) && stints.stints.length && store.stintRows.length === 0) {
        store.setStintRows(stints.stints as ApiStintRow[]);
      }
    } catch {
      /* charts keep last-known laps */
    }
  }

  private frameQuery(asOf: Date, extra?: { refresh?: boolean; full?: boolean }): string {
    const driver = useRaceStore.getState().arisDriver ?? useRaceStore.getState().focusDriver;
    const qs = new URLSearchParams({
      session_key: String(this.sessionKey),
      as_of: asOf.toISOString(),
      year: String(this.year),
      round_number: String(this.round),
    });
    if (driver) qs.set("driver", driver);
    if (extra?.refresh) qs.set("refresh", "1");
    if (extra?.full) qs.set("full", "1");
    else if (this.lastFrameAsOf) qs.set("prev_as_of", this.lastFrameAsOf);
    return qs.toString();
  }

  /** Warm FastF1 30s ahead of the playhead so a late datapoint can still land. */
  private prefetchAhead(asOf: Date) {
    if (this.sessionKey == null) return;
    const now = performance.now();
    if (now - this.lastPrefetchAt < 2000) return;
    this.lastPrefetchAt = now;
    const ahead = new Date(asOf.getTime() + LOOKAHEAD_S * 1000);
    if (this.dateEnd && ahead > this.dateEnd) return;
    void fetchJson(`${API_BASE}/api/live/replay-frame?${this.frameQuery(ahead, { full: true })}`, 20000);
  }

  private async warmLookahead() {
    if (this.sessionKey == null || !this.dateStart) return;
    const origin = this.dateStart.getTime() + this.greenFlagS * 1000;
    for (const extra of [10, 20, LOOKAHEAD_S]) {
      if (this.closed) return;
      this.prefetchAhead(new Date(origin + extra * 1000));
    }
  }

  private async tick() {
    if (this.closed || this.sessionKey == null || !this.dateStart || this.inFlight) return;
    this.inFlight = true;
    const store = useRaceStore.getState();
    const seek = store.seekLap;
    const seeking = seek != null;
    if (seek != null) {
      this.elapsedS = this.lapToElapsed(seek);
      store.clearSeekLap();
    }
    const now = performance.now();
    const dt = (now - this.lastWall) / 1000;
    this.lastWall = now;
    const playing = store.isPlaying && store.consolePlayState === "racing";
    if (playing) this.elapsedS += dt * store.playbackSpeed;
    const origin = this.dateStart.getTime() + this.greenFlagS * 1000;
    let asOf = new Date(origin + this.elapsedS * 1000);
    if (this.dateEnd && asOf > this.dateEnd) {
      if (this.elapsedS < 2) {
        asOf = new Date(Math.min(origin, this.dateEnd.getTime()));
      } else {
        store.setIsPlaying(false);
        store.setRaceFinished(true);
        this.inFlight = false;
        return;
      }
    }
    try {
      const refresh = this.refreshOnce;
      this.refreshOnce = false;
      const pollStart = Date.now();
      const frame = await fetchJson(
        `${API_BASE}/api/live/replay-frame?${this.frameQuery(asOf, { refresh, full: seeking })}`,
        20000,
      );
      const pollDuration = Date.now() - pollStart;
      this.pollDurations.push(pollDuration);
      if (this.pollDurations.length > 80) this.pollDurations.shift();
      if (pollDuration > 300) {
        console.warn(`[ReplayFrameFeed] slow poll: ${pollDuration}ms`);
      }
      if (this.pollDurations.length === 20 || this.pollDurations.length === 80) {
        const sorted = [...this.pollDurations].sort((a, b) => a - b);
        const p50 = sorted[Math.floor(sorted.length * 0.5)];
        const p95 = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))];
        console.info(`[ReplayFrameFeed] poll p50=${p50}ms p95=${p95}ms n=${sorted.length}`);
      }
      if (this.closed) return;
      if (!frame) {
        if (playing) this.elapsedS = Math.max(0, this.elapsedS - dt * store.playbackSpeed);
        this.prefetchAhead(asOf);
        return;
      }
      if (frame?.date_start) this.dateStart = new Date(frame.date_start);
      if (frame?.date_end) this.dateEnd = new Date(frame.date_end);
      if (frame?.green_flag_s && !this.greenFlagS) this.greenFlagS = Number(frame.green_flag_s);
      if (typeof frame?.duration_s === "number") this.durationS = Math.max(0, frame.duration_s - this.greenFlagS);
      setFeedStatus("connected", 0);
      this.applyPayload(
        {
          status: {
            is_live: true,
            current_lap: frame?.timing?.current_lap,
            total_laps: store.totalLaps,
            session_flag: frame?.session_flag,
          },
          timing: frame?.timing,
          weather: frame?.weather,
          positions: frame?.positions,
          ghost: frame?.ghost,
          ghost_reason: frame?.ghost_reason ?? null,
          is_delta: Boolean(frame?.is_delta),
          circuit_path: frame?.circuit_path,
          markers: frame?.markers,
          pit_lane_x: frame?.pit_lane_x,
          pit_lane_y: frame?.pit_lane_y,
        },
        seeking,
      );
      if (frame?.as_of) this.lastFrameAsOf = String(frame.as_of);
      this.prefetchAhead(asOf);
      const latest = useRaceStore.getState();
      if (Object.keys(latest.cars).length || (frame?.timing?.rows || []).length) {
        latest.setWaiting(false);
      }
      const flag = String(frame?.session_flag || "").toUpperCase();
      const finishedFlag = flag === "FINISHED" || flag === "CHEQUERED" || flag.includes("FINISH");
      if (
        playing &&
        ((finishedFlag && latest.totalLaps > 0 && latest.currentLap >= latest.totalLaps) ||
          (latest.totalLaps > 0 && latest.currentLap >= latest.totalLaps && this.dateEnd && asOf >= this.dateEnd))
      ) {
        latest.setRaceFinished(true);
        latest.setIsPlaying(false);
      }
      if (now - this.lastLapsAt > 900) {
        this.lastLapsAt = now;
        void this.pollReplayLaps(asOf);
      }
    } catch {
      if (playing) this.elapsedS = Math.max(0, this.elapsedS - dt * store.playbackSpeed);
      setFeedStatus("reconnecting");
    } finally {
      this.inFlight = false;
    }
  }

  private applyPayload(payload: SsePayload, seeking = false) {
    if (this.closed) return;
    const store = useRaceStore.getState();
    const incomingRows = payload.timing?.rows ?? [];
    const incomingPos = payload.positions?.positions ?? [];
    const timingRows = payload.is_delta ? mergeByDriverCode(this.lastTimingRows, incomingRows) : incomingRows;
    const positions = payload.is_delta ? mergeByDriverCode(this.lastPositions, incomingPos) : incomingPos;
    this.lastTimingRows = timingRows;
    this.lastPositions = positions;
    const lap = payload.status?.current_lap ?? payload.timing?.current_lap ?? store.currentLap;
    const frameTotal = payload.status?.total_laps;
    if (frameTotal && frameTotal > 0) store.setTotalLaps(frameTotal);
    const total = frameTotal ?? store.totalLaps;
    applyCircuitPath(payload);
    if (!seeking && lap) store.setCurrentLap(Math.max(1, lap));
    if (payload.status?.session_flag) store.setRacePhase(sessionFlagToPhase(payload.status.session_flag));
    const raining = payload.weather?.rainfall ?? payload.timing?.rainfall;
    if (typeof raining === "boolean") store.setRainfall(raining);
    const cars = mapTimingAndPositions(timingRows, positions, store.gridDrivers, total || store.totalLaps || 1, lap || 1);
    const fp = timingFingerprint(timingRows, positions);
    if (Object.keys(cars).length && (fp !== this.lastFp || Object.keys(store.cars).length === 0)) {
      this.lastFp = fp;
      const merged = mergeCars(store.cars, cars);
      if (merged !== store.cars) store.setCars(merged);
    }
    applyGhost(payload);
    setFeedStatus("connected", 0);
  }

  disconnect() {
    this.closed = true;
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}

async function fetchJson(url: string, timeoutMs = 12000): Promise<any> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(id);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
