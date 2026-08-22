import { DurableObject } from "cloudflare:workers";

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
        return Response.json(
          {
            error:
              "The ARIS UI is on Cloudflare. The FastAPI broker is not. Upgrade to Workers Paid and run npm run deploy:container, or set API_ORIGIN to a running uvicorn host.",
          },
          { status: 503 },
        );
      }
      const target = new URL(url.pathname + url.search, origin);
      return fetch(target, {
        method: request.method,
        headers: request.headers,
        body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      });
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
