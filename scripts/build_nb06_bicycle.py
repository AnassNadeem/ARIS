"""Generate + execute notebooks/06-bicycle-vs-actual.ipynb with embedded outputs.

One-shot builder so the notebook's predicted-vs-actual cells run against real
Bahrain 2024 data and the residual figure is saved. Re-runnable; safe to delete.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "notebooks" / "06-bicycle-vs-actual.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text)


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text)


cells = [
    md(
        "# 06 — Bicycle model vs actual (Phase 3, Wk 5 Day 2)\n\n"
        "The hand-coded single-track bicycle model (`aris.physics.bicycle`) predicts a "
        "**single, constant** grip-limited lap time — it has no per-lap inputs yet (no fuel "
        "mass, no tyre age, no thermal model, no downforce). We overlay that flat prediction "
        "on one of Verstappen's real green-flag stints at Bahrain 2024.\n\n"
        "It is **wrong on purpose.** The gap between the flat line and the real laps — and the "
        "*shape* of that gap against tyre age — is exactly the residual the Wk-6 ML will learn, "
        "fed through the leakage-safe builder the Day-1 tripwire guards."
    ),
    code(
        "from pathlib import Path\n\n"
        "import fastf1\n"
        "import matplotlib.pyplot as plt\n\n"
        "from aris.physics.bicycle import Car, StintState, bahrain_2024, predict_lap_time\n"
        "from aris.physics.stint import detect_stints, filter_clean_laps\n\n"
        'REPO = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()\n'
        'CACHE = REPO / "fastf1_cache"\n'
        "fastf1.Cache.enable_cache(str(CACHE))\n"
        'print("fastf1", fastf1.__version__)'
    ),
    code(
        'session = fastf1.get_session(2024, "Bahrain", "R")\n'
        "session.load(telemetry=False, laps=True, weather=False, messages=False)\n\n"
        "enriched = detect_stints(session.laps)\n"
        "clean = filter_clean_laps(enriched)\n"
        'ver = clean[clean["Driver"] == "VER"].copy()\n\n'
        "# pick VER's longest green-flag stint\n"
        'longest = ver.groupby("StintId").size().idxmax()\n'
        'stint = ver[ver["StintId"] == longest].sort_values("LapNumber")\n'
        'compound = stint["Compound"].iloc[0]\n'
        'print(f"VER stint {longest}: {len(stint)} green laps, compound {compound}")'
    ),
    code(
        "# the bicycle model: one constant prediction for the whole stint\n"
        "predicted_s = predict_lap_time(StintState(Car(), bahrain_2024()))\n"
        'actual_s = stint["LapTimeS"].to_numpy()\n'
        'tyre_life = stint["TyreLife"].to_numpy()\n'
        'median_s = stint["LapTimeS"].median()\n\n'
        'print(f"bicycle predicted (constant): {predicted_s:.2f} s")\n'
        'print(f"actual stint median:          {median_s:.2f} s")\n'
        'print(f"mean residual (actual-pred):  {(actual_s - predicted_s).mean():.2f} s")'
    ),
    code(
        'fig, ax = plt.subplots(figsize=(9, 4.5))\n'
        'ax.plot(tyre_life, actual_s, "o-", color="#1f77b4", label="actual (VER)")\n'
        'ax.axhline(predicted_s, color="#d62728", ls="--", lw=2,\n'
        '           label=f"bicycle model (constant {predicted_s:.1f} s)")\n'
        'ax.set_xlabel("tyre life (laps)")\n'
        'ax.set_ylabel("lap time (s)")\n'
        'ax.set_title("Bahrain 2024 — VER stint: bicycle model vs actual")\n'
        'ax.grid(True, alpha=0.3)\n'
        "ax.legend()\n"
        "fig.tight_layout()\n"
        'out = REPO / "assets" / "screenshots" / "wk5-bicycle-vs-actual.png"\n'
        'fig.savefig(out, dpi=110, bbox_inches="tight")\n'
        'print("saved", out.relative_to(REPO))'
    ),
    md(
        "## Where the model is wrong — the residual map for Wk 6\n\n"
        "The flat red line is the entire bicycle model: no per-lap dynamics. The real laps "
        "depart from it in three structured ways, and **structure is learnable signal**:\n\n"
        "1. **Cold-tyre effect** — the first lap or two of the stint sit high (warming the "
        "compound into its working window). The model has no thermal state.\n"
        "2. **Fuel burn** — the car sheds ~1.6 kg/lap; lighter ⇒ faster, a gentle downward "
        "drift across the stint. The Day-2 model is mass-invariant (grip-limited cornering "
        "cancels mass), so it misses this entirely — Day 3 adds the linear fuel term.\n"
        "3. **Tyre degradation** — late in the stint laps climb again as grip falls off. No "
        "deg model here.\n\n"
        "Below: the residual `actual − predicted` against tyre life. Its slope and curvature "
        "are what the Wk-6 residual model is trained to reproduce."
    ),
    code(
        "residual = actual_s - predicted_s\n"
        "fig, ax = plt.subplots(figsize=(9, 4))\n"
        'ax.plot(tyre_life, residual, "o-", color="#2ca02c")\n'
        'ax.axhline(0, color="k", lw=0.8)\n'
        'ax.set_xlabel("tyre life (laps)")\n'
        'ax.set_ylabel("residual: actual - bicycle (s)")\n'
        'ax.set_title("Residual the Wk-6 ML will learn (VER, Bahrain 2024)")\n'
        'ax.grid(True, alpha=0.3)\n'
        "fig.tight_layout()\n"
        "plt.show()"
    ),
    md(
        "## Day 3 — fuel-burn + pit-loss terms\n\n"
        "Two linear corrections on top of the physics. **Fuel:** the car carries ~110 kg at "
        "the start and burns ~1.7 kg/lap; at ~0.03 s per kg, a full tank costs ~3 s vs empty. "
        "**Pit-loss:** an in/out lap costs ~21 s at Bahrain. We model fuel across the whole "
        "race so this (final) stint correctly sits at low fuel, then re-score."
    ),
    code(
        "from aris.eval.scoring import mae\n\n"
        "START_FUEL_KG, BURN_PER_LAP_KG = 110.0, 1.7\n"
        'lap_no = stint["LapNumber"].to_numpy()\n'
        "fuel_kg = (START_FUEL_KG - BURN_PER_LAP_KG * (lap_no - 1)).clip(min=0)\n\n"
        "track = bahrain_2024()\n"
        "pred_base = [predicted_s] * len(actual_s)\n"
        "pred_fuel = [predict_lap_time(StintState(Car(), track, fuel_kg=f)) for f in fuel_kg]\n\n"
        "mae_base = mae(actual_s, pred_base)\n"
        "mae_fuel = mae(actual_s, pred_fuel)\n"
        'print(f"fuel over this stint: {fuel_kg.max():.0f} -> {fuel_kg.min():.0f} kg")\n'
        'print(f"MAE physics-only:     {mae_base:.2f} s")\n'
        'print(f"MAE + fuel term:      {mae_fuel:.2f} s")\n'
        "full = predict_lap_time(StintState(Car(), track, fuel_kg=100.0))\n"
        "green_ref = predict_lap_time(StintState(Car(), track, fuel_kg=30.0))\n"
        "pit = predict_lap_time(StintState(Car(), track, fuel_kg=30.0, pit_lap=True))\n"
        'print(f"full-tank (100 kg) lap: {full:.2f} s  (+{full - predicted_s:.2f} vs empty)")\n'
        'print(f"in/out (pit) lap:       {pit:.2f} s  (+{pit - green_ref:.2f} pit-loss)")'
    ),
    code(
        "fig, ax = plt.subplots(figsize=(9, 4.5))\n"
        'ax.plot(tyre_life, actual_s, "o-", color="#1f77b4", label="actual (VER)")\n'
        'ax.plot(tyre_life, pred_base, "--", color="#d62728", lw=2, label="physics only (flat)")\n'
        'ax.plot(tyre_life, pred_fuel, "-", color="#ff7f0e", lw=2, label="physics + fuel")\n'
        'ax.set_xlabel("tyre life (laps)")\n'
        'ax.set_ylabel("lap time (s)")\n'
        'ax.set_title("Bahrain 2024 — VER: adding the fuel-burn slope")\n'
        'ax.grid(True, alpha=0.3)\n'
        "ax.legend()\n"
        "fig.tight_layout()\n"
        'out2 = REPO / "assets" / "screenshots" / "wk5-bicycle-fuel.png"\n'
        'fig.savefig(out2, dpi=110, bbox_inches="tight")\n'
        'print("saved", out2.relative_to(REPO))'
    ),
    md(
        "### Honest read: the fuel term is correct but doesn't help here\n\n"
        "The fuel term adds the right *shape* — a gentle downward slope as the tank empties — "
        "but it's worth <1 s across this light-fuel final stint, while the error it's competing "
        "with is the **~16 s constant bias from missing downforce**. So the MAE barely moves "
        "(and, because the base is already too slow, adding any positive fuel penalty nudges it "
        "slightly *worse* on this stint). That is exactly the expected outcome, not a failure: "
        "a near-constant bias is an intercept the **Wk-6 residual ML learns trivially**, and the "
        "fuel/pit-loss terms exist to get the per-lap *structure* right, not the absolute level. "
        "Hand-tuning the grip constant to erase the bias would over-fit one stint and generalise "
        "badly — the residual model closes it from data instead."
    ),
]

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.11"},
}

ep = ExecutePreprocessor(timeout=300, kernel_name="python3")
ep.preprocess(nb, {"metadata": {"path": str(REPO / "notebooks")}})

nbf.write(nb, OUT)
print("wrote + executed", OUT.relative_to(REPO))
