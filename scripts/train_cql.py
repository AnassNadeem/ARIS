#!/usr/bin/env python
"""Train the CQL Q-network on the offline pit/stay dataset."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn  # noqa: F401 — kept for the specified training surface
import torch.nn.functional as F  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aris.models.cql import (  # noqa: E402
    CONT_INDICES,
    QNetwork,
    build_state_vector,
    cql_loss,
    raw_state_vector,
)
from aris.state import RaceState  # noqa: E402


def _row_to_state(row: pd.Series) -> RaceState:
    total_laps = int(row["lap_number"]) + int(row["laps_remaining"])
    hist = [
        float(row["gap_h3"]),
        float(row["gap_h2"]),
        float(row["gap_h1"]),
        float(row["gap_ahead"]),
    ]
    return RaceState(
        session_id=0,
        driver_id=0,
        driver_code=str(row["driver_code"]),
        driver_name=str(row["driver_code"]),
        year=int(row["race_year"]),
        round_no=int(row["round_number"]),
        country="",
        lap_number=int(row["lap_number"]),
        compound=str(row["compound"]),
        tyre_life=int(row["tyre_life"]),
        fuel_kg=float(row["fuel_kg"]),
        laps_remaining=int(row["laps_remaining"]),
        total_laps=total_laps,
        lag1_pace=float(row["lag1_s"]),
        lag2_pace=float(row["lag2_s"]),
        stint_roll3=float(row["roll3_s"]),
        gap_ahead_s=float(row["gap_ahead"]),
        gap_ahead_history=hist,
        position=int(row["position"]),
        stint_number=int(row["stint"]),
        track_status=str(row["track_status"]),
        rainfall=bool(row["rainfall"]),
    )


def compute_normalisation(train_df: pd.DataFrame, _cont_features: list[str]) -> dict:
    """Fit z-score stats on train-set raw continuous features only."""
    raws = np.stack([raw_state_vector(_row_to_state(row)) for _, row in train_df.iterrows()])
    cont = raws[:, CONT_INDICES]
    means = cont.mean(axis=0).astype(float).tolist()
    stds = cont.std(axis=0).astype(float).tolist()
    return {
        "cont_indices": list(CONT_INDICES),
        "means": means,
        "stds": stds,
        "hidden": 128,
    }


def build_tensor(df: pd.DataFrame, normalisation: dict) -> torch.Tensor:
    if df.empty:
        return torch.zeros((0, 18), dtype=torch.float32)
    xs = [
        build_state_vector(_row_to_state(row), normalisation)
        for _, row in df.iterrows()
    ]
    return torch.tensor(np.stack(xs), dtype=torch.float32)


def main(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    df = pd.read_parquet(args.dataset)
    print(f"Loaded {len(df)} transitions")
    print("Action dist:", df["action"].value_counts().to_dict())

    years = sorted(int(y) for y in df["race_year"].unique())
    n_val = max(1, int(len(years) * 0.2))
    val_years = years[-n_val:]
    train_df = df[~df["race_year"].isin(val_years)]
    val_df = df[df["race_year"].isin(val_years)]
    if train_df.empty:
        # Single-year smoke sets would otherwise have an empty train split.
        n_val_rows = max(1, int(len(df) * 0.2))
        val_df = df.iloc[-n_val_rows:]
        train_df = df.iloc[:-n_val_rows]
        val_years = list(val_df["race_year"].unique())
    print(f"Train: {len(train_df)}, Val: {len(val_df)}")
    print(f"Val years: {val_years}")

    cont_features = [
        "tyre_life_norm_raw",
        "lag1_delta_raw",
        "lag2_delta_raw",
        "gap_ahead_norm_raw",
        "gap_trend_raw",
        "fuel_norm_raw",
        "laps_remaining_norm_raw",
        "position_norm_raw",
        "stint_norm_raw",
        "race_frac_raw",
    ]
    normalisation = compute_normalisation(train_df, cont_features)
    normalisation["hidden"] = int(args.hidden)
    Path(args.norm_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.norm_output).write_text(json.dumps(normalisation, indent=2), encoding="utf-8")

    x_train = build_tensor(train_df, normalisation)
    y_train = torch.tensor(train_df["action"].to_numpy(), dtype=torch.long)
    r_train = torch.tensor(train_df["return_g"].to_numpy(), dtype=torch.float32)
    x_val = build_tensor(val_df, normalisation)
    y_val = torch.tensor(val_df["action"].to_numpy(), dtype=torch.long)
    r_val = torch.tensor(val_df["return_g"].to_numpy(), dtype=torch.float32)

    model = QNetwork(hidden=args.hidden)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)

    best_val = float("inf")
    best_epoch = 0
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        model.train()
        perm = torch.randperm(len(x_train))
        train_loss = 0.0
        n_batches = 0
        for i in range(0, len(x_train), args.batch_size):
            idx = perm[i : i + args.batch_size]
            loss = cql_loss(
                model, x_train[idx], y_train[idx], r_train[idx], alpha=args.alpha
            )
            opt.zero_grad()
            loss.backward()
            opt.step()
            train_loss += float(loss.item())
            n_batches += 1
        train_loss /= max(n_batches, 1)

        model.eval()
        with torch.no_grad():
            if len(x_val) == 0:
                val_loss = train_loss
            else:
                val_loss = float(
                    cql_loss(model, x_val, y_val, r_val, alpha=args.alpha).item()
                )

        if epoch % 10 == 0 or epoch == 1:
            print(f"Epoch {epoch:3d} | train {train_loss:.4f} | val {val_loss:.4f}")

        if val_loss < best_val:
            best_val = val_loss
            best_epoch = epoch
            torch.save(model.state_dict(), args.output)

    print(f"\nBest val {best_val:.4f} at epoch {best_epoch}")
    print(f"Saved: {args.output}")

    model.load_state_dict(torch.load(args.output, map_location="cpu", weights_only=True))
    model.eval()
    with torch.no_grad():
        probe = x_val if len(x_val) else x_train
        q_val = model(probe)
        q_stay = q_val[:, 0].numpy()
        q_hard = q_val[:, 3].numpy()
        print(f"Q[STAY_OUT] range: [{q_stay.min():.3f}, {q_stay.max():.3f}]")
        print(f"Q[PIT_HARD] range: [{q_hard.min():.3f}, {q_hard.max():.3f}]")
        argmax = q_val.argmax(dim=1).numpy()
        print("Argmax Q dist on val:", Counter(argmax.tolist()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the CQL Q-network")
    parser.add_argument("--dataset", default="data/cql_dataset.parquet")
    parser.add_argument("--output", default="models/cql_q_network.pt")
    parser.add_argument("--norm-output", default="models/cql_normalisation.json")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--hidden", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    main(parser.parse_args())
