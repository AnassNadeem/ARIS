import { useRaceStore } from "@/store/raceStore";
import { ghostCarFromTick } from "@/lib/ghostCar";
import type { ARISRecommendation, CarState, CommsEntry, GhostTickData, RacePhase } from "@/lib/types";

type WireMessage =
  | { type: "tick"; cars: Record<string, CarState>; lap: number; total_laps: number; phase: RacePhase; ghost?: GhostTickData | null }
  | { type: "aris_recommendation"; recommendation: ARISRecommendation }
  | { type: "aris_comms"; entry: CommsEntry }
  | { type: "ghost_update"; car: CarState };

const RECONNECT_DELAY_MS = 5000;

export class RaceSocket {
  private url: string;
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closedByUser = false;
  private hasConnectedOnce = false;
  // Track last seen phase so we push phaseHistory only on transitions, not
  // every tick. Prevents duplicate SC/VSC entries in LapTimesChart bands.
  private lastPhase: RacePhase | null = null;
  onOpen?: () => void;
  onFailure?: () => void;

  constructor(url: string) {
    this.url = url;
  }

  connect() {
    this.closedByUser = false;
    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    const store = useRaceStore;
    store.getState().setConnectionStatus(this.hasConnectedOnce ? "reconnecting" : "connecting");

    this.ws.onopen = () => {
      this.hasConnectedOnce = true;
      store.getState().setConnectionStatus("connected", 0);
      this.send({ type: "sync_request" });
      this.onOpen?.();
    };

    this.ws.onmessage = (ev) => {
      let msg: WireMessage;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      this.handleMessage(msg);
    };

    this.ws.onclose = () => {
      if (this.closedByUser) return;
      store.getState().setConnectionStatus("reconnecting");
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.onFailure?.();
    };
  }

  private handleMessage(msg: WireMessage) {
    const store = useRaceStore.getState();
    switch (msg.type) {
      case "tick":
        store.setCars(msg.cars);
        store.setCurrentLap(msg.lap);
        store.setTotalLaps(msg.total_laps);
        store.setRacePhase(msg.phase);
        // Push phaseHistory only on transitions to avoid duplicate band entries.
        if (msg.phase !== this.lastPhase) {
          store.pushPhaseHistory({ lap: msg.lap, phase: msg.phase });
          this.lastPhase = msg.phase;
        }
        // Sync ghost state: update both the positional CarState (for map/tower)
        // and the full GhostTickData (for GhostDelta panel).
        if (msg.ghost) {
          store.setGhostData(msg.ghost);
          const real = store.cars[msg.ghost.driver_code] ?? null;
          store.setGhostCar(ghostCarFromTick(msg.ghost, real, msg.lap, msg.total_laps));
        } else if (msg.ghost === null) {
          store.setGhostCar(null);
          store.setGhostData(null);
        }
        break;
      case "aris_recommendation":
        store.setPendingRecommendation(msg.recommendation);
        // If ARIS sends a STRATEGY_RESET, push a special comms entry
        // (no approve/deny card — it's a status update).
        if (msg.recommendation.label === "STRATEGY_RESET") {
          const nc = msg.recommendation.narration_context as Record<string, unknown>;
          const freeTyre = nc.free_tyre_change ? " Free tyre change available." : "";
          store.pushComms({
            id: `reset-${msg.recommendation.lap}-${Date.now()}`,
            lap: msg.recommendation.lap,
            source: "ARIS_RESET",
            text: `${nc.reason ?? "Strategy recalculating from current state."}${freeTyre}`,
            timestamp: Date.now(),
          });
          // Do NOT set pendingRecommendation — no action card for resets.
          store.setPendingRecommendation(null);
        }
        break;
      case "aris_comms":
        store.pushComms(msg.entry);
        break;
      case "ghost_update":
        store.setGhostCar(msg.car);
        break;
    }
  }

  send(payload: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.closedByUser) this.connect();
    }, RECONNECT_DELAY_MS);
  }

  disconnect() {
    this.closedByUser = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}

/** WS origin from build-time env. Never defaults to localhost in production. */
export function publicWsBase(): string {
  const explicit = (process.env.NEXT_PUBLIC_WS_BASE ?? "").trim().replace(/\/$/, "");
  if (explicit) return explicit;
  const api = (process.env.NEXT_PUBLIC_API_BASE ?? "").trim().replace(/\/$/, "");
  if (api.startsWith("https://")) return `wss://${api.slice("https://".length)}`;
  if (api.startsWith("http://")) return `ws://${api.slice("http://".length)}`;
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  }
  return "";
}

export function createRaceSocket(mode: "live" | "replay", sessionKey?: string): RaceSocket {
  const base = publicWsBase();
  const url = mode === "live" ? `${base}/api/live/stream` : `${base}/api/replay/stream?session=${sessionKey ?? ""}`;
  return new RaceSocket(url);
}
