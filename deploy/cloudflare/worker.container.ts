import { Container, getContainer } from "@cloudflare/containers";

export class ArisApi extends Container<Env> {
  defaultPort = 8080;
  requiredPorts = [8080];
  sleepAfter = "48h";
  enableInternet = true;
  pingEndpoint = "/health";

  override onActivityExpired(): boolean {
    return true;
  }
}

export default {
  async fetch(request, env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/") || url.pathname === "/health") {
      const container = getContainer(env.ARIS_API, "live");
      await container.startAndWaitForPorts({
        ports: [8080],
        startOptions: {
          enableInternet: true,
          envVars: {
            OPENF1_USERNAME: env.OPENF1_USERNAME ?? "",
            OPENF1_PASSWORD: env.OPENF1_PASSWORD ?? "",
            ARIS_DB_URL: env.ARIS_DB_URL ?? "",
          },
        },
        cancellationOptions: {
          instanceGetTimeoutMS: 60_000,
          portReadyTimeoutMS: 180_000,
        },
      });
      return container.fetch(request);
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
