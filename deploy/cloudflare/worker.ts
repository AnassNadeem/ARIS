import { DurableObject } from "cloudflare:workers";
import { withSecurityHeaders } from "./securityHeaders";

/** Kept because the first deploy registered this Durable Object class. */
export class ArisApi extends DurableObject<Env> {
  override fetch(): Response {
    return Response.json(
      { error: "Cloudflare Containers need the Workers Paid plan." },
      { status: 503 },
    );
  }
}

function apiOrigin(env: Env): string {
  return ((env as Env & { API_ORIGIN?: string }).API_ORIGIN ?? "").replace(/\/$/, "");
}

export default {
  async fetch(request, env): Promise<Response> {
    const url = new URL(request.url);
    const api = url.pathname.startsWith("/api/") || url.pathname === "/health";
    if (api) {
      const origin = apiOrigin(env);
      if (!origin) {
        return withSecurityHeaders(
          Response.json(
            {
              error:
                "Production API is Heroku, not this Worker. Set API_ORIGIN only for local-dev tunneling (scripts/aris-home-tunnel.ps1).",
            },
            { status: 503 },
          ),
        );
      }
      const target = new URL(url.pathname + url.search, origin);
      const headers = new Headers();
      for (const name of ["accept", "accept-language", "content-type", "authorization"]) {
        const value = request.headers.get(name);
        if (value) headers.set(name, value);
      }
      const heavy =
        url.pathname.includes("/replay-frame") ||
        url.pathname.includes("/replay-path") ||
        url.pathname.includes("/replay-ready") ||
        url.pathname.includes("/history") ||
        /\/api\/circuit\/.+\/(map|preview|characteristics)$/.test(url.pathname);
      try {
        const upstream = await fetch(target, {
          method: request.method,
          headers,
          body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
          signal: AbortSignal.timeout(heavy ? 90_000 : 25_000),
        });
        return withSecurityHeaders(upstream);
      } catch (err) {
        const detail = err instanceof Error ? err.message : "tunnel fetch failed";
        return withSecurityHeaders(
          Response.json(
            { error: "ARIS backend is warming up. Retry shortly.", detail },
            { status: 503 },
          ),
        );
      }
    }
    return withSecurityHeaders(await env.ASSETS.fetch(request));
  },
} satisfies ExportedHandler<Env>;
