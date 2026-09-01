import { expect, type Page, test } from "@playwright/test";

const DRIVERS_2024 = [
  { driver_code: "VER", full_name: "Max Verstappen", team_name: "Red Bull Racing", team_colour: "#3671C6", driver_number: 1 },
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

test("race_field.json 404 shows unavailable, not a spinner", async ({ page }) => {
  await stubSetupApis(page);
  await page.route("**/race_field.json*", async (route) => {
    await route.fulfill({ status: 404, body: "not found" });
  });
  await page.goto("/replay?year=2024&round=1");
  const raceCard = page.getByRole("button", { name: /R1\b/ }).first();
  await expect(raceCard).toBeVisible({ timeout: 20_000 });
  await raceCard.click();
  const startBtn = page.getByRole("button", { name: /Start Race/i });
  await expect(startBtn).toBeEnabled({ timeout: 20_000 });
  await startBtn.click();
  await expect(page.getByText("Race data unavailable — check back soon")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".animate-pulse")).toHaveCount(0);
});
