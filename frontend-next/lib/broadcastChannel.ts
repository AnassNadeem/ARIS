// Forwards live race-state ticks from the main console window to any
// torn-off panel windows opened via the ⤢ button, using BroadcastChannel.
// The main window is always the data source; torn-off windows only listen.

export const ARIS_CHANNEL_NAME = "aris-race-state";

export type BroadcastMessage =
  | { type: "tick"; payload: unknown }
  | { type: "ghost_update"; payload: unknown }
  | { type: "aris_comms"; payload: unknown }
  | { type: "aris_recommendation"; payload: unknown };

let channel: BroadcastChannel | null = null;

function getChannel(): BroadcastChannel | null {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") return null;
  if (!channel) channel = new BroadcastChannel(ARIS_CHANNEL_NAME);
  return channel;
}

export function broadcastRaceState(message: BroadcastMessage) {
  getChannel()?.postMessage(message);
}

export function subscribeRaceState(handler: (message: BroadcastMessage) => void): () => void {
  const ch = getChannel();
  if (!ch) return () => {};
  const listener = (ev: MessageEvent<BroadcastMessage>) => handler(ev.data);
  ch.addEventListener("message", listener);
  return () => ch.removeEventListener("message", listener);
}

/**
 * Opens a panel's content in a new browser window (the ⤢ "tear-off" button).
 * The new window loads `/panel/[panelId]` which renders just that panel and
 * subscribes to the same BroadcastChannel for live data.
 */
export function tearOffPanel(panelId: string, title: string) {
  if (typeof window === "undefined") return;
  const url = `${window.location.origin}/panel/${panelId}`;
  window.open(url, `aris-panel-${panelId}`, "width=640,height=480,menubar=no,toolbar=no,location=no");
  document.title = title; // no-op safeguard; real title set inside the child window
}
