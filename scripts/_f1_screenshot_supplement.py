"""Supplemental after-shots: initial setup, what-if with rec, postrace."""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from scripts._f1_screenshot import (  # noqa: E402
    BASE,
    VIEWPORT,
    click_button,
    click_radio,
    dump_debug,
    shot,
    wait_app,
)

OUT = _ROOT / "results" / "f1_after"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport=VIEWPORT).new_page()
        page.set_default_timeout(60_000)

        page.goto(f"{BASE}/Strategy", wait_until="domcontentloaded")
        wait_app(page, "You are the race engineer")
        page.wait_for_timeout(1200)
        shot(page, OUT / "01_strategy_initial_setup.png")

        click_button(page, "Start / Reset session")
        wait_app(page, "Lock strategy")
        page.wait_for_timeout(1500)
        click_button(page, "Lock strategy & start race")
        page.wait_for_timeout(2500)
        try:
            click_radio(page, "Pause")
        except Exception as exc:  # noqa: BLE001
            print(f"pause: {exc}", flush=True)

        click_radio(page, "What-if")
        try:
            page.wait_for_selector("text=vs stay out", timeout=120_000)
        except PlaywrightTimeout:
            dump_debug(page, OUT, "whatif_slow")
        shot(page, OUT / "05_strategy_whatif.png")

        click_radio(page, "Watch")
        page.wait_for_timeout(800)
        # F1.2: skip is behind Show technical detail (default off).
        try:
            page.get_by_text("Show technical detail", exact=True).click()
            page.wait_for_timeout(800)
        except Exception as exc:  # noqa: BLE001
            print(f"technical toggle: {exc}", flush=True)
        try:
            click_button(page, "Skip to chequered flag")
        except PlaywrightTimeout:
            dump_debug(page, OUT, "skip_missing")
            print("skip button missing", flush=True)
        try:
            page.wait_for_selector("text=Exported to", timeout=180_000)
        except PlaywrightTimeout:
            dump_debug(page, OUT, "postrace_skip")
        page.wait_for_timeout(1500)
        shot(page, OUT / "07_strategy_postrace.png")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
