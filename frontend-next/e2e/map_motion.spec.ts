import { expect, type Page, test } from "@playwright/test";

const DRIVERS_2024 = [
  { driver_code: "VER", full_name: "Max Verstappen", team_name: "Red Bull Racing", team_colour: "#3671C6", driver_number: 1 },
  { driver_code: "PER", full_name: "Sergio Perez", team_name: "Red Bull Racing", team_colour: "#3671C6", driver_number: 11 },
  { driver_code: "LEC", full_name: "Charles Leclerc", team_name: "Ferrari", team_colour: "#E8002D", driver_number: 16 },
  { driver_code: "NOR", full_name: "Lando Norris", team_name: "McLaren", team_colour: "#FF8000", driver_number: 4 },
];

const CALENDAR_2024 = {
  rounds: [
    { round_number: 1, name: "Bahrain", circuit_name: "Sakhir", circuit_key: "bahrain", country: "Bahrain", date_race: "2024-03-02", status: "COMPLETED", is_sprint_weekend: false, total_laps: 57 },
  ],
};

async function stubSetupApis(page: Page) {
  await page.route("**/api/drivers/**", async (route) => {
    await route.fulfill({ json: { drivers: DRIVERS_2024 } });
  });
  await page.route("**/api/calendar/**", async (route) => {
    await route.fulfill({ json: CALENDAR_2024 });
  });
}

async function startReplay(page: Page) {
  await stubSetupApis(page);
  await page.goto("/replay?year=2024&round=1");
  const arisOn = page.getByRole("button", { name: /^On$/i });
  await expect(arisOn).toBeVisible({ timeout: 20_000 });
  await arisOn.click();
  const raceCard = page.getByRole("button", { name: /R1\b/ }).first();
  await expect(raceCard).toBeVisible({ timeout: 20_000 });
  await raceCard.click();
  const continueBtn = page.getByRole("button", { name: /Continue with/i });
  await expect(continueBtn).toBeEnabled({ timeout: 20_000 });
  await continueBtn.click();
  const driverBtn = page.getByRole("button", { name: /#\d+\s+VER\b/ });
  await expect(driverBtn).toBeVisible({ timeout: 20_000 });
  await driverBtn.click();
  await page.getByRole("button", { name: /Get Strategies/i }).click();
  const rec = page.getByRole("button", { name: /Recommended/i }).first();
  await expect(rec).toBeVisible({ timeout: 30_000 });
  await rec.click();
  await page.getByRole("button", { name: /Start Race/i }).click();
  await page.waitForURL(/\/replay\/console/, { timeout: 60_000 });
  const consoleStart = page.getByRole("button", { name: /Start Race/i });
  if (await consoleStart.isVisible().catch(() => false)) {
    await consoleStart.click();
  }
  await expect.poll(async () => page.locator('[data-testid^="tower-row-"]').count(), { timeout: 30_000 }).toBeGreaterThanOrEqual(10);
}

function readDots(page: Page) {
  return page.locator('[data-testid^="car-dot-"]').evaluateAll((els) =>
    els
      .filter((el) => {
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return false;
        if (Number(style.opacity) === 0) return false;
        return true;
      })
      .map((el) => {
        const id = el.getAttribute("data-testid") || "";
        const cx = Number(el.getAttribute("cx"));
        const cy = Number(el.getAttribute("cy"));
        let x = cx;
        let y = cy;
        if (!Number.isFinite(x) || !Number.isFinite(y) || (x === 0 && y === 0)) {
          const t = el.getAttribute("transform") || "";
          const m = t.match(/translate\(\s*([-0-9.eE]+)\s*,\s*([-0-9.eE]+)\s*\)/);
          if (m) {
            x = Number(m[1]);
            y = Number(m[2]);
          }
        }
        return { id, x, y };
      })
      .filter((d) => Number.isFinite(d.x) && Number.isFinite(d.y)),
  );
}

async function sampleMotion(page: Page, ms: number, everyMs: number) {
  const samples: { t: number; dots: { id: string; x: number; y: number }[] }[] = [];
  const start = Date.now();
  while (Date.now() - start < ms) {
    samples.push({ t: Date.now() - start, dots: await readDots(page) });
    await page.waitForTimeout(everyMs);
  }
  return samples;
}

function assertSmooth(samples: { t: number; dots: { id: string; x: number; y: number }[] }[], label: string) {
  expect(samples.length, `${label}: not enough samples`).toBeGreaterThan(20);
  const byId = new Map<string, { t: number; x: number; y: number }[]>();
  for (const s of samples) {
    for (const d of s.dots) {
      const arr = byId.get(d.id) ?? [];
      arr.push({ t: s.t, x: d.x, y: d.y });
      byId.set(d.id, arr);
    }
  }
  expect(byId.size, `${label}: no visible cars`).toBeGreaterThanOrEqual(8);

  let maxStep = 0;
  let worstId = "";
  for (const [id, pts] of byId) {
    if (pts.length < 8) continue;
    let stuckMs = 0;
    for (let i = 1; i < pts.length; i++) {
      const dt = pts[i].t - pts[i - 1].t;
      const dist = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
      if (dist > maxStep) {
        maxStep = dist;
        worstId = id;
      }
      if (dist < 0.2) stuckMs += dt;
      else stuckMs = 0;
      expect(stuckMs, `${label}: ${id} stuck ${stuckMs}ms at t=${pts[i].t}`).toBeLessThan(450);
    }
  }
  expect(maxStep, `${label}: teleport ${maxStep.toFixed(1)}px on ${worstId}`).toBeLessThan(80);
}

test.describe("map motion", () => {
  test("cars crawl smoothly at 1x and 4x with no teleports or stalls", async ({ page }) => {
    test.setTimeout(180_000);
    await startReplay(page);
    await expect.poll(async () => (await readDots(page)).length, { timeout: 20_000 }).toBeGreaterThanOrEqual(8);
    const origin = await readDots(page);
    await expect
      .poll(
        async () => {
          const now = await readDots(page);
          return now.some((d) => {
            const prev = origin.find((p) => p.id === d.id);
            return prev != null && Math.hypot(d.x - prev.x, d.y - prev.y) > 2;
          });
        },
        { timeout: 15_000 },
      )
      .toBe(true);

    const at1x = await sampleMotion(page, 8000, 50);
    assertSmooth(at1x, "1x");

    await page.getByRole("button", { name: "4×" }).click();
    await page.waitForTimeout(200);
    const at4x = await sampleMotion(page, 8000, 50);
    assertSmooth(at4x, "4x");
  });
});
