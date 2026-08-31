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

/** Public R2 bucket. Used to proxy `/r2replay/*` in `next dev` when public/r2replay is absent. */
function r2PublicOrigin(): string {
  return (
    process.env.R2_PUBLIC_ORIGIN ||
    "https://pub-9429cde26be84c4c8034f0b5873b9a7d.r2.dev"
  ).replace(/\/$/, "");
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
          const r2 = r2PublicOrigin();
          const rules: { source: string; destination: string }[] = [
            // afterFiles: public/r2replay wins when present; this covers machines without a local copy
            { source: "/r2replay/:path*", destination: `${r2}/:path*` },
          ];
          if (backend) {
            rules.push(
              { source: "/api/:path*", destination: `${backend}/api/:path*` },
              {
                source: "/static_replays/:path*",
                destination: `${backend}/static_replays/:path*`,
              },
            );
          }
          return rules;
        },
      }
    : {}),
};

export default nextConfig;
