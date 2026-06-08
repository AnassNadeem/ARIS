"""Leave-one-race-out cross-validation folds. The split the leakage tripwire enforces."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd


def race_by_race_folds(
    df: pd.DataFrame, race_col: str = "race_id"
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield (train_idx, test_idx) holding each race out once — zero race overlap per fold.

    Each unique value of `race_col` is the test set exactly once; the train set is
    every other race. Indices are positional (0..len(df)-1) so callers can use
    `df.iloc[train_idx]` / `df.iloc[test_idx]` regardless of the frame's own index.
    """
    if race_col not in df.columns:
        raise ValueError(f"race_col {race_col!r} not in frame columns: {list(df.columns)}")
    races = df[race_col].to_numpy()
    positions = np.arange(len(df))
    for race in pd.unique(races):
        test_mask = races == race
        yield positions[~test_mask], positions[test_mask]
