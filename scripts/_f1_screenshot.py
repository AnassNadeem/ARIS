"""Playwright screenshots of the ARIS Streamlit dashboard.

Usage:
    python scripts/_f1_screenshot.py before
    python scripts/_f1_screenshot.py after
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright

_ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8501"
VIEWPORT = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}


def _out_dir(which: str) -> Path:
    d = _ROOT / "results" / ("f1_before" if which == "before" else "f1_after")
    d.mkdir(parents=True, exist_ok=True)
    return d


def wait_app(page: Page, needle: str, timeout_ms: int = 60_000) -> None:
    page.wait_for_selector("text=" + needle, timeout=timeout_ms)
    # Streamlit reruns leave a brief spinner; give widgets a beat to settle.
    page.wait_for_timeout(800)


def shot(page: Page, path: Path, full_page: bool = True) -> None:
    page.screenshot(path=str(path), full_page=full_page)
    print(f"wrote {path.name} ({path.stat().st_size} bytes)", flush=True)


def click_button(page: Page, name: str, timeout_ms: int = 15_000) -> None:
    page.get_by_role("button", name=name).click(timeout=timeout_ms)
    page.wait_for_timeout(1500)


def open_selectbox(page: Page, nth: int) -> None:
    page.locator('[data-testid="stSelectbox"]').nth(nth).click()
    page.wait_for_timeout(400)


def choose_option(page: Page, label: str) -> None:
    loc = page.get_by_role("option", name=label)
    if loc.count() == 0:
        loc = page.get_by_text(label, exact=True)
    loc.first.click()
    page.wait_for_timeout(800)


def click_radio(page: Page, label: str) -> None:
    # Streamlit radio options are labels inside stRadio.
    radio = page.locator('[data-testid="stRadio"]')
    target = radio.get_by_text(label, exact=True)
    if target.count() == 0:
        target = page.get_by_text(label, exact=True)
    target.first.click()
    page.wait_for_timeout(1200)


def dump_debug(page: Page, out: Path, tag: str) -> None:
    html_path = out / f"_debug_{tag}.html"
    html_path.write_text(page.content(), encoding="utf-8")
    shot(page, out / f"_debug_{tag}.png")
    print(f"debug dump {tag}", flush=True)


def capture(which: str) -> int:
    out = _out_dir(which)
    after = which == "after"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        page.set_default_timeout(45_000)

        # --- Home / landing (after) or lap explorer (before, was home) ---
        page.goto(BASE, wait_until="domcontentloaded")
        try:
            wait_app(page, "ARIS")
        except PlaywrightTimeout:
            dump_debug(page, out, "home_timeout")
            raise
        page.wait_for_timeout(1500)
        if after:
            shot(page, out / "00_home.png")
            page.goto(f"{BASE}/Lap_explorer", wait_until="domcontentloaded")
            try:
                wait_app(page, "Lap-time explorer")
            except PlaywrightTimeout:
                dump_debug(page, out, "explorer_timeout")
            page.wait_for_timeout(4000)
        shot(page, out / "00_lap_explorer.png")

        # --- Strategy: initial setup ---
        page.goto(f"{BASE}/Strategy", wait_until="domcontentloaded")
        try:
            wait_app(page, "You are the race engineer")
        except PlaywrightTimeout:
            dump_debug(page, out, "strategy_timeout")
            raise
        page.wait_for_timeout(1500)
        shot(page, out / "01_strategy_initial_setup.png")

        # --- Pre-race: 2025 Netherlands (default year; has FP/Q) ---
        try:
            click_button(page, "Start / Reset session")
            wait_app(page, "Pre-race strategy")
        except PlaywrightTimeout:
            dump_debug(page, out, "prerace_nl")
        page.wait_for_timeout(2500)
        shot(page, out / "02_strategy_prerace.png")

        # --- Blank weekend form: 2024 race-only ingest ---
        page.goto(f"{BASE}/Strategy", wait_until="domcontentloaded")
        wait_app(page, "Strategy")
        page.wait_for_timeout(1000)
        try:
            open_selectbox(page, 0)  # Season
            choose_option(page, "2024")
            page.wait_for_timeout(1500)
            # 2024 default is Netherlands (race-only) — same blank-form case as Bahrain.
            # Prefer Bahrain if the option is visible.
            try:
                open_selectbox(page, 1)
                page.get_by_text("Bahrain", exact=False).first.click(timeout=5000)
                page.wait_for_timeout(800)
            except Exception:
                page.keyboard.press("Escape")
            click_button(page, "Start / Reset session")
            page.wait_for_timeout(4000)
        except Exception as exc:  # noqa: BLE001
            print(f"bahrain prerace interaction failed: {exc}", flush=True)
            dump_debug(page, out, "prerace_bahrain")
        shot(page, out / "02b_strategy_prerace_bahrain_blank_form.png")

        # --- Live: restart default (2025 NL), lock strategy ---
        page.goto(f"{BASE}/Strategy", wait_until="domcontentloaded")
        wait_app(page, "Strategy")
        page.wait_for_timeout(1000)
        click_button(page, "Start / Reset session")
        try:
            wait_app(page, "Lock strategy")
        except PlaywrightTimeout:
            dump_debug(page, out, "lock_missing")
        try:
            click_button(page, "Lock strategy & start race")
        except PlaywrightTimeout:
            dump_debug(page, out, "lock_click")
            raise
        # Let the first tick + recommend land, then pause.
        page.wait_for_timeout(5000)
        try:
            click_radio(page, "Pause")
        except Exception as exc:  # noqa: BLE001
            print(f"pause click failed: {exc}", flush=True)
            dump_debug(page, out, "pause")
        page.wait_for_timeout(1500)
        shot(page, out / "03_strategy_live_watch.png")

        try:
            click_radio(page, "Ask")
            page.wait_for_timeout(1500)
            shot(page, out / "04_strategy_ask.png")
        except Exception as exc:  # noqa: BLE001
            print(f"ask failed: {exc}", flush=True)
            dump_debug(page, out, "ask")

        try:
            click_radio(page, "What-if")
            try:
                page.wait_for_selector("text=vs stay out", timeout=120_000)
            except PlaywrightTimeout:
                print("WARN: what-if recommend did not finish in 120s", flush=True)
            shot(page, out / "05_strategy_whatif.png")
        except Exception as exc:  # noqa: BLE001
            print(f"whatif failed: {exc}", flush=True)
            dump_debug(page, out, "whatif")

        try:
            click_radio(page, "Replay")
            page.wait_for_timeout(35000)
            shot(page, out / "06_strategy_replay.png")
        except Exception as exc:  # noqa: BLE001
            print(f"replay failed: {exc}", flush=True)
            dump_debug(page, out, "replay")

        # --- Postrace ---
        try:
            click_radio(page, "Watch")
            click_radio(page, "4x")
        except Exception as exc:  # noqa: BLE001
            print(f"4x failed: {exc}", flush=True)

        deadline = time.time() + (600 if after else 240)
        found = False
        while time.time() < deadline:
            body = page.inner_text("body")
            if "Post-race" in body or "Exported to" in body:
                found = True
                break
            page.wait_for_timeout(2000)
        if not found:
            print("WARN: postrace not reached within deadline", flush=True)
            dump_debug(page, out, "postrace_timeout")
        page.wait_for_timeout(1500)
        shot(page, out / "07_strategy_postrace.png")

        if after:
            mobile = browser.new_context(viewport=MOBILE)
            mpage = mobile.new_page()
            mpage.set_default_timeout(45_000)
            mpage.goto(BASE, wait_until="domcontentloaded")
            try:
                wait_app(mpage, "ARIS")
            except PlaywrightTimeout:
                dump_debug(mpage, out, "mobile_home")
            mpage.wait_for_timeout(1200)
            shot(mpage, out / "08_mobile_home.png")
            mpage.goto(f"{BASE}/Strategy", wait_until="domcontentloaded")
            try:
                wait_app(mpage, "Strategy")
            except PlaywrightTimeout:
                dump_debug(mpage, out, "mobile_strategy")
            mpage.wait_for_timeout(1200)
            shot(mpage, out / "08_mobile_strategy.png")
            mobile.close()

        browser.close()
    return 0


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "before"
    if which not in ("before", "after"):
        print("usage: _f1_screenshot.py [before|after]", flush=True)
        raise SystemExit(2)
    raise SystemExit(capture(which))
