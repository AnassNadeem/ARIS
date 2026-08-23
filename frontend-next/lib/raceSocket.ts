import { useRaceStore } from "@/store/raceStore";
import type { ARISRecommendation, CarState, CommsEntry, RacePhase } from "@/lib/types";

type WireMessage =
  | { type: "tick"; cars: Record<string, CarState>; lap: number; total_laps: number; phase: RacePhase }
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
        break;
      case "aris_recommendation":
        store.setPendingRecommendation(msg.recommendation);
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

export function createRaceSocket(mode: "live" | "replay", sessionKey?: string): RaceSocket {
  const base = process.env.NEXT_PUBLIC_WS_BASE ?? "ws://localhost:8000";
  const url = mode === "live" ? `${base}/api/live/stream` : `${base}/api/replay/stream?session=${sessionKey ?? ""}`;
  return new RaceSocket(url);
}
