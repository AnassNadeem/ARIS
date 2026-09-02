import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
process.chdir(appRoot);

// Workers Builds (dashboard) is still `cd frontend-next && npm run dev`.
// On Cloudflare that must compile `out/` and exit; locally keep `next dev`.
if (process.env.WORKERS_CI === "1") {
  const ci = spawnSync("npm", ["ci"], { stdio: "inherit", shell: true });
  if (ci.status) process.exit(ci.status ?? 1);
  const build = spawnSync("npm", ["run", "build:static"], {
    stdio: "inherit",
    shell: true,
    env: process.env,
  });
  process.exit(build.status ?? 1);
}

const extra = process.argv.slice(2);
const dev = spawnSync("npx", ["next", "dev", ...extra], {
  stdio: "inherit",
  shell: true,
  env: process.env,
});
process.exit(dev.status ?? 1);
