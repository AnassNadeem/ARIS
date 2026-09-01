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
