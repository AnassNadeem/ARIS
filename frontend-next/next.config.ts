import path from "path";
import type { NextConfig } from "next";

function backendOrigin(): string | null {
  const explicit = (process.env.ARIS_BACKEND_ORIGIN ?? "").trim().replace(/\/$/, "");
  if (explicit) return explicit;
  // Local `next dev` proxies to the laptop broker. Production (Cloudflare Pages)
  // must set NEXT_PUBLIC_API_BASE / ARIS_BACKEND_ORIGIN — never ship localhost.
  if (process.env.NODE_ENV !== "production") {
    return "http://127.0.0.1:8765";
  }
  return null;
}

const staticExport = Boolean(process.env.CF_PAGES);

const nextConfig: NextConfig = {
  ...(staticExport ? { output: "export" as const, images: { unoptimized: true } } : {}),
  turbopack: {
    root: path.join(__dirname),
  },
  ...(!staticExport
    ? {
        async rewrites() {
          const backend = backendOrigin();
          if (!backend) return [];
          return [
            { source: "/api/:path*", destination: `${backend}/api/:path*` },
            {
              source: "/static_replays/:path*",
              destination: `${backend}/static_replays/:path*`,
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
