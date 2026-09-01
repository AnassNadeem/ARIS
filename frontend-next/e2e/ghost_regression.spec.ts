import { expect, type Locator, type Page, test } from "@playwright/test";

const DRIVERS_2024 = [
  { driver_code: "VER", full_name: "Max Verstappen", team_name: "Red Bull Racing", team_colour: "#3671C6", driver_number: 1 },
  { driver_code: "PER", full_name: "Sergio Perez", team_name: "Red Bull Racing", team_colour: "#3671C6", driver_number: 11 },
  { driver_code: "LEC", full_name: "Charles Leclerc", team_name: "Ferrari", team_colour: "#E8002D", driver_number: 16 },
  { driver_code: "SAI", full_name: "Carlos Sainz", team_name: "Ferrari", team_colour: "#E8002D", driver_number: 55 },
  { driver_code: "NOR", full_name: "Lando Norris", team_name: "McLaren", team_colour: "#FF8000", driver_number: 4 },
  { driver_code: "PIA", full_name: "Oscar Piastri", team_name: "McLaren", team_colour: "#FF8000", driver_number: 81 },
  { driver_code: "RUS", full_name: "George Russell", team_name: "Mercedes", team_colour: "#27F4D2", driver_number: 63 },
  { driver_code: "HAM", full_name: "Lewis Hamilton", team_name: "Mercedes", team_colour: "#27F4D2", driver_number: 44 },
  { driver_code: "ALO", full_name: "Fernando Alonso", team_name: "Aston Martin", team_colour: "#00665E", driver_number: 14 },
  { driver_code: "STR", full_name: "Lance Stroll", team_name: "Aston Martin", team_colour: "#00665E", driver_number: 18 },
  { driver_code: "GAS", full_name: "Pierre Gasly", team_name: "Alpine", team_colour: "#0093CC", driver_number: 10 },
  { driver_code: "OCO", full_name: "Esteban Ocon", team_name: "Alpine", team_colour: "#0093CC", driver_number: 31 },
  { driver_code: "ALB", full_name: "Alex Albon", team_name: "Williams", team_colour: "#1868DB", driver_number: 23 },
  { driver_code: "SAR", full_name: "Logan Sargeant", team_name: "Williams", team_colour: "#1868DB", driver_number: 2 },
  { driver_code: "TSU", full_name: "Yuki Tsunoda", team_name: "RB", team_colour: "#6692FF", driver_number: 22 },
  { driver_code: "RIC", full_name: "Daniel Ricciardo", team_name: "RB", team_colour: "#6692FF", driver_number: 3 },
  { driver_code: "HUL", full_name: "Nico Hulkenberg", team_name: "Haas", team_colour: "#B6BABD", driver_number: 27 },
  { driver_code: "MAG", full_name: "Kevin Magnussen", team_name: "Haas", team_colour: "#B6BABD", driver_number: 20 },
  { driver_code: "BOT", full_name: "Valtteri Bottas", team_name: "Sauber", team_colour: "#52E252", driver_number: 77 },
  { driver_code: "ZHO", full_name: "Zhou Guanyu", team_name: "Sauber", team_colour: "#52E252", driver_number: 24 },
];

const CALENDAR_2024 = {
  rounds: [
    { round_number: 1, name: "Bahrain", circuit_name: "Sakhir", circuit_key: "bahrain", country: "Bahrain", date_race: "2024-03-02", status: "COMPLETED", is_sprint_weekend: false, total_laps: 57 },
    { round_number: 2, name: "Saudi Arabia", circuit_name: "Jeddah", circuit_key: "jeddah", country: "Saudi Arabia", date_race: "2024-03-09", status: "COMPLETED", is_sprint_weekend: false, total_laps: 50 },
    { round_number: 3, name: "Australia", circuit_name: "Melbourne", circuit_key: "albert_park", country: "Australia", date_race: "2024-03-24", status: "COMPLETED", is_sprint_weekend: false, total_laps: 58 },
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

async function waitForTower(page: Page, timeout = 30_000) {
  await expect
    .poll(async () => page.locator('[data-testid^="tower-row-"]').count(), { timeout })
    .toBeGreaterThanOrEqual(10);
}

async function startReplay(page: Page, year: number, round: number, driver = "VER") {
  await stubSetupApis(page);
  await page.goto(`/replay?year=${year}&round=${round}`);
  const arisOn = page.getByRole("button", { name: /^On$/i });
  await expect(arisOn).toBeVisible({ timeout: 20_000 });
  await arisOn.click();
  const raceCard = page.getByRole("button", { name: new RegExp(`R${round}\\b`) }).first();
  await expect(raceCard).toBeVisible({ timeout: 20_000 });
  await raceCard.click();
  const continueBtn = page.getByRole("button", { name: /Continue with/i });
  await expect(continueBtn).toBeEnabled({ timeout: 20_000 });
  await continueBtn.click();
  const driverBtn = page.getByRole("button", { name: new RegExp(`#\\d+\\s+${driver}\\b`) });
  await expect(driverBtn).toBeVisible({ timeout: 20_000 });
  await driverBtn.click();
  await page.getByRole("button", { name: /Get Strategies/i }).click();
  const rec = page.getByRole("button", { name: /Recommended/i }).first();
  await expect(rec).toBeVisible({ timeout: 30_000 });
  await rec.click();
  await page.getByRole("button", { name: /Start Race/i }).click();
  await page.waitForURL(/\/replay\/console/, { timeout: 60_000 });
  // The console has its own lights-out "Start Race" gate (consolePlayState
  // "ready"/"starting" -> "racing"). No analytics — sector times, speed,
  // timing tower rows — are populated before this click (clean pre-race
  // state); click it before waiting for the tower, or without it the replay
  // clock never advances and seeks land but time never moves afterwards.
  const consoleStart = page.getByRole("button", { name: /Start Race/i });
  if (await consoleStart.isVisible().catch(() => false)) {
    await consoleStart.click();
  }
  await waitForTower(page);
}

async function dotPos(locator: Locator) {
  await expect(locator).toBeVisible({ timeout: 15_000 });
  return locator.evaluate((el) => {
    const cx = el.getAttribute("cx");
    const cy = el.getAttribute("cy");
    if (cx != null && cy != null && Number.isFinite(Number(cx)) && Number.isFinite(Number(cy))) {
      const x = Number(cx);
      const y = Number(cy);
      if (x !== 0 || y !== 0) return { x, y };
    }
    const t = el.getAttribute("transform") || "";
    const m = t.match(/translate\(\s*([-0-9.eE]+)\s*,\s*([-0-9.eE]+)\s*\)/);
    if (m) return { x: Number(m[1]), y: Number(m[2]) };
    const box = el.getBoundingClientRect();
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  });
}

async function seekToLap(page: Page, lap: number) {
  const scrubber = page.getByTestId("lap-scrubber");
  await expect(scrubber).toBeAttached({ timeout: 15_000 });
  await scrubber.evaluate((el, value) => {
    const input = el as HTMLInputElement & { _valueTracker?: { setValue: (v: string) => void } };
    // React tracks a range input's "previous value" on a hidden value
    // tracker to decide whether to fire its synthetic onChange. Setting
    // `.value` directly (as any programmatic seek must) leaves the tracker
    // already pointing at the new value, so a plain dispatchEvent("input")
    // is silently swallowed and the app never actually seeks — the DOM
    // shows the new value but the store's currentLap never moves. Reset the
    // tracker to the old value first so React detects the change for real.
    const previousValue = input.value;
    input.value = String(value);
    input._valueTracker?.setValue(previousValue);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, lap);
  await expect
    .poll(async () => Number(await scrubber.inputValue()), { timeout: 10_000 })
    .toBe(lap);
}

test.describe("ghost regression", () => {
  // Hidden by default (NEXT_PUBLIC_ARIS_GHOST_MAP is unset). The map ghost
  // dot is gated until the backend GPS-projection / path_frac wrap bug is
  // fixed — a misplaced ghost on the circuit undermines the demo. Re-enable
  // this alignment check when ghostMapFeatureEnabled() ships on.
  test.skip("Ghost starts with real car", async ({ page }) => {
    await startReplay(page, 2024, 1, "VER");
    const ghost = page.getByTestId("ghost-dot");
    const ver = page.getByTestId("car-dot-VER");
    await expect(ghost).toBeVisible({ timeout: 15_000 });
    await expect(ver).toBeVisible({ timeout: 15_000 });
    await page.waitForFunction(() => {
      const g = document.querySelector('[data-testid="ghost-dot"]');
      const v = document.querySelector('[data-testid="car-dot-VER"]');
      if (!g || !v) return false;
      const gt = g.getAttribute("transform") || "";
      const vt = v.getAttribute("transform") || "";
      const gc = g.getAttribute("cx");
      const vc = v.getAttribute("cx");
      return Boolean(gt || (gc != null && Number(gc) !== 0)) && Boolean(vt || (vc != null && Number(vc) !== 0));
    });
    const gPos = await dotPos(ghost);
    const vPos = await dotPos(ver);
    const dist = Math.hypot(gPos.x - vPos.x, gPos.y - vPos.y);
    expect(dist, `ghost ${JSON.stringify(gPos)} vs VER ${JSON.stringify(vPos)}`).toBeLessThanOrEqual(5);
  });

  test("Ghost map dot is hidden by default; tower ARIS row is present", async ({ page }) => {
    await startReplay(page, 2024, 1, "VER");
    await expect(page.getByTestId("ghost-dot")).toHaveCount(0);
    await expect(page.getByTestId("ghost-tower-row")).toBeVisible({ timeout: 15_000 });
  });

  test("Ghost does not stay P1", async ({ page }) => {
    await startReplay(page, 2024, 1, "VER");
    const samples: string[] = [];
    for (const lap of [15, 20, 25]) {
      await seekToLap(page, lap);
      const row = page.getByTestId("ghost-tower-row");
      await expect(row).toBeVisible({ timeout: 15_000 });
      samples.push((await row.getAttribute("data-position")) ?? "");
    }
    const allP1 = samples.every((p) => p === "1");
    expect(allP1, `ghost positions at laps 15/20/25: ${samples.join(",")}`).toBe(false);
  });

  test("DNF drivers always at bottom", async ({ page }) => {
    await startReplay(page, 2024, 3, "VER");
    const scrubber = page.getByTestId("lap-scrubber");
    await expect(scrubber).toBeAttached({ timeout: 15_000 });
    const maxLap = Number(await scrubber.getAttribute("max"));
    await seekToLap(page, Number.isFinite(maxLap) && maxLap > 0 ? maxLap : 57);
    const rows = page.locator("[data-testid^='tower-row-'], [data-testid='ghost-tower-row']");
    await expect.poll(async () => rows.count(), { timeout: 15_000 }).toBeGreaterThanOrEqual(10);
    const flags = await rows.evaluateAll((els) => els.map((el) => el.getAttribute("data-dnf")));
    let seenDnf = false;
    for (const flag of flags) {
      if (flag === "true") seenDnf = true;
      if (seenDnf) expect(flag).toBe("true");
    }
  });

  test("Strategy panel shows ARIS stint plan and highlights the current stint", async ({ page }) => {
    await startReplay(page, 2024, 1, "VER");
    const panel = page.getByTestId("strategy-panel");
    await expect(panel).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("strategy-current-stint")).toBeVisible({ timeout: 15_000 });
  });

  test("Timing tower shows IN PITS while the ghost is in its pit window", async ({ page }) => {
    await startReplay(page, 2024, 1, "VER");
    // Read the ghost's actual pit lap from the strategy panel instead of
    // hardcoding one, so this stays correct if the recommended plan changes.
    const panelText = await page.getByTestId("strategy-panel").innerText();
    const pitLapMatch = panelText.match(/L1[–-](\d+)/);
    const pitLap = pitLapMatch ? Number(pitLapMatch[1]) : 9;

    const row = page.getByTestId("ghost-tower-row");
    // seekToLap always lands at lap-start (progress ~0); the ghost's pit
    // window sits near the end of the in-lap (~84% progress). Seek to the
    // pit lap itself, then let fast playback carry it through the pit-entry
    // point while polling for the status text.
    await seekToLap(page, pitLap);
    await page.getByRole("button", { name: "25×" }).click();
    await expect
      .poll(async () => (await row.innerText()).includes("IN PITS"), { timeout: 10_000, intervals: [150] })
      .toBe(true);
  });

  test("Car dots do not all disappear", async ({ page }) => {
    await startReplay(page, 2024, 1, "VER");
    await page.getByRole("button", { name: "4×" }).click();
    const counts: number[] = [];
    const deadline = Date.now() + 20_000;
    while (Date.now() < deadline) {
      const visible = await page.locator('[data-testid^="car-dot-"]').evaluateAll((els) =>
        els.filter((el) => {
          const style = window.getComputedStyle(el);
          if (style.display === "none" || style.visibility === "hidden") return false;
          if (Number(style.opacity) === 0) return false;
          return true;
        }).length,
      );
      counts.push(visible);
      expect(visible, `visible car dots dropped to ${visible} (history ${counts.join(",")})`).toBeGreaterThanOrEqual(15);
      await page.waitForTimeout(2000);
    }
    expect(counts.length).toBeGreaterThanOrEqual(8);
  });
});
