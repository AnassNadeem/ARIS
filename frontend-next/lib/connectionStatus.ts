export type FeedConnectionStatus = "connecting" | "connected" | "disconnected" | "reconnecting";

export type ConnectionStatusView = {
  label: string;
  note: string | null;
  tone: "ok" | "warn" | "lost";
};

/** Copy for the console feed badge. No lagMs — that value is hardcoded 0. */
export function connectionStatusView(
  status: FeedConnectionStatus,
  consoleMode: "live" | "replay",
): ConnectionStatusView {
  if (status === "disconnected") {
    return { label: "FEED LOST", note: null, tone: "lost" };
  }
  if (status === "connecting") {
    return { label: "CONNECTING…", note: null, tone: "warn" };
  }
  if (status === "reconnecting") {
    return { label: "RECONNECTING…", note: null, tone: "warn" };
  }
  if (consoleMode === "live") {
    return { label: "CONNECTED", note: "OpenF1 live · ~5–7s delay", tone: "ok" };
  }
  return { label: "CONNECTED  FastF1", note: null, tone: "ok" };
}
