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

async function startReplay(page: Page, opts: { startRace?: boolean } = {}) {
  const startRace = opts.startRace !== false;
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
  if (!startRace) {
    await expect.poll(async () => page.locator('[data-testid^="tower-row-"]').count(), { timeout: 30_000 }).toBeGreaterThanOrEqual(10);
    return;
  }
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
        const frac = Number(el.getAttribute("data-path-frac"));
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
        return { id, x, y, frac: Number.isFinite(frac) ? frac : null };
      })
      .filter((d) => Number.isFinite(d.x) && Number.isFinite(d.y)),
  );
}

async function readTowerOrder(page: Page) {
  return page.locator('[data-testid^="tower-row-"][data-dnf="false"]').evaluateAll((els) =>
    els.map((el) => ({
      id: (el.getAttribute("data-testid") || "").replace("tower-row-", ""),
      position: Number(el.getAttribute("data-position")),
    })),
  );
}

function wrappedDelta(from: number, to: number): number {
  let d = to - from;
  if (d < -0.5) d += 1;
  return d;
}

function assertMapMatchesTower(
  dots: { id: string; frac: number | null }[],
  tower: { id: string; position: number }[],
  label: string,
) {
  const byCode = new Map(dots.map((d) => [d.id.replace("car-dot-", ""), d]));
  const comparable = tower.filter((row) => {
    const dot = byCode.get(row.id);
    return dot != null && dot.frac != null && dot.frac > 0.08 && dot.frac < 0.92;
  });
  if (comparable.length < 4) return;
  for (let i = 0; i < comparable.length; i++) {
    for (let j = i + 1; j < comparable.length; j++) {
      const ahead = comparable[i];
      const behind = comparable[j];
      const a = byCode.get(ahead.id)!.frac!;
      const b = byCode.get(behind.id)!.frac!;
      expect(
        a + 0.03,
        `${label}: ${ahead.id} (P${ahead.position}, frac=${a}) should be ahead of ${behind.id} (P${behind.position}, frac=${b})`,
      ).toBeGreaterThanOrEqual(b);
    }
  }
}

async function sampleMotion(page: Page, ms: number, everyMs: number) {
  const samples: {
    t: number;
    dots: { id: string; x: number; y: number; frac: number | null }[];
    tower: { id: string; position: number }[];
  }[] = [];
  const start = Date.now();
  while (Date.now() - start < ms) {
    const [dots, tower] = await Promise.all([readDots(page), readTowerOrder(page)]);
    samples.push({ t: Date.now() - start, dots, tower });
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
    let lastFrac = new Map<string, number>();
    for (const sample of at1x) {
      assertMapMatchesTower(
        sample.dots.map((d) => ({ id: d.id, frac: d.frac })),
        sample.tower,
        `1x t=${sample.t}`,
      );
      for (const d of sample.dots) {
        if (d.frac == null) continue;
        const prev = lastFrac.get(d.id);
        if (prev != null) {
          expect(wrappedDelta(prev, d.frac), `${d.id}: uncapped delta ${prev} → ${d.frac}`).toBeLessThan(0.25);
        }
        lastFrac.set(d.id, d.frac);
      }
    }

    await page.getByRole("button", { name: "4×" }).click();
    await page.waitForTimeout(200);
    const at4x = await sampleMotion(page, 8000, 50);
    assertSmooth(at4x, "4x");
    lastFrac = new Map();
    for (const sample of at4x) {
      for (const d of sample.dots) {
        if (d.frac == null) continue;
        const prev = lastFrac.get(d.id);
        if (prev != null) {
          expect(wrappedDelta(prev, d.frac), `${d.id}: uncapped 4x delta ${prev} → ${d.frac}`).toBeLessThan(0.25);
        }
        lastFrac.set(d.id, d.frac);
      }
    }
  });

  test("dropping 50x to 1x does not freeze the map", async ({ page }) => {
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

    await page.getByRole("button", { name: "50×" }).click();
    const at50 = await readDots(page);
    await expect
      .poll(
        async () => {
          const now = await readDots(page);
          return now.some((d) => {
            const prev = at50.find((p) => p.id === d.id);
            return prev != null && Math.hypot(d.x - prev.x, d.y - prev.y) > 20;
          });
        },
        { timeout: 8_000 },
      )
      .toBe(true);

    await page.getByRole("button", { name: "1×" }).click();
    await page.waitForTimeout(200);
    const afterDrop = await sampleMotion(page, 3000, 50);
    expect(afterDrop.length, "50x→1x: not enough samples").toBeGreaterThan(20);
    const byId = new Map<string, { t: number; x: number; y: number }[]>();
    for (const s of afterDrop) {
      for (const d of s.dots) {
        const arr = byId.get(d.id) ?? [];
        arr.push({ t: s.t, x: d.x, y: d.y });
        byId.set(d.id, arr);
      }
    }
    let fleetMoved = false;
    for (const [id, pts] of byId) {
      if (pts.length < 8) continue;
      let stuckMs = 0;
      const first = pts[0];
      const last = pts[pts.length - 1];
      if (Math.hypot(last.x - first.x, last.y - first.y) > 2) fleetMoved = true;
      for (let i = 1; i < pts.length; i++) {
        const dt = pts[i].t - pts[i - 1].t;
        const dist = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
        stuckMs = dist < 0.15 ? stuckMs + dt : 0;
        expect(stuckMs, `50x→1x: ${id} frozen ${stuckMs}ms at t=${pts[i].t}`).toBeLessThan(1800);
      }
    }
    expect(fleetMoved, "50x→1x: cars should keep crawling after the drop").toBe(true);
  });

  test("grid order at lights-out matches qualifying grid_position", async ({ page }) => {
    test.setTimeout(180_000);
    await startReplay(page, { startRace: false });
    await expect.poll(async () => (await readDots(page)).length, { timeout: 20_000 }).toBeGreaterThanOrEqual(8);
    const tower = await readTowerOrder(page);
    const dots = await readDots(page);
    const byCode = new Map(dots.map((d) => [d.id.replace("car-dot-", ""), d]));
    const withFrac = tower.filter((row) => byCode.get(row.id)?.frac != null);
    expect(withFrac.length).toBeGreaterThanOrEqual(8);
    const pole = withFrac[0];
    const last = withFrac[withFrac.length - 1];
    const poleFrac = byCode.get(pole.id)!.frac!;
    const lastFrac = byCode.get(last.id)!.frac!;
    const poleErr = Math.min(Math.abs(poleFrac), Math.abs(poleFrac - 1));
    expect(poleErr, `pole ${pole.id} frac=${poleFrac}`).toBeLessThan(0.02);
    expect(lastFrac === 0 ? 1 : lastFrac).toBeGreaterThan(0.9);
    await expect(page.getByTestId("speed-hud-value")).toHaveCount(0);
  });

  test("speed HUD and ghost delta populate for the chosen driver", async ({ page }) => {
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
    await expect
      .poll(async () => /\d/.test((await page.getByTestId("speed-hud-value").innerText()) || ""), { timeout: 15_000 })
      .toBe(true);
    await expect(page.getByTestId("speed-hud-ghost-delta")).toBeVisible({ timeout: 15_000 });
  });
});
