"""Tests for aris.models.cv — the leave-one-race-out splitter."""

import numpy as np
import pandas as pd
import pytest

from aris.models.cv import race_by_race_folds


def _frame(race_ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"race_id": race_ids, "x": range(len(race_ids))})


class TestRaceByRaceFolds:
    def test_one_fold_per_unique_race(self):
        df = _frame(["A", "A", "B", "B", "C"])
        folds = list(race_by_race_folds(df))
        assert len(folds) == 3  # A, B, C

    def test_no_race_on_both_sides_of_a_fold(self):
        df = _frame(["A", "A", "B", "B", "C", "C"])
        races = df["race_id"].to_numpy()
        for train_idx, test_idx in race_by_race_folds(df):
            train_races = set(races[train_idx])
            test_races = set(races[test_idx])
            assert train_races.isdisjoint(test_races)

    def test_each_race_is_test_set_exactly_once(self):
        df = _frame(["A", "A", "B", "C", "C", "C"])
        races = df["race_id"].to_numpy()
        held_out: list[str] = []
        for _, test_idx in race_by_race_folds(df):
            unique_test = set(races[test_idx])
            assert len(unique_test) == 1  # exactly one race held out
            held_out.append(unique_test.pop())
        assert sorted(held_out) == ["A", "B", "C"]

    def test_train_and_test_partition_the_frame(self):
        df = _frame(["A", "B", "B", "C"])
        n = len(df)
        for train_idx, test_idx in race_by_race_folds(df):
            combined = np.concatenate([train_idx, test_idx])
            assert sorted(combined.tolist()) == list(range(n))  # no gaps, no overlap

    def test_indices_are_positional_not_label(self):
        # non-default index must not leak into the returned positions
        df = _frame(["A", "A", "B"])
        df.index = [10, 20, 30]
        for train_idx, test_idx in race_by_race_folds(df):
            assert train_idx.max(initial=-1) < len(df)
            assert test_idx.max(initial=-1) < len(df)

    def test_custom_race_col(self):
        df = pd.DataFrame({"gp": ["X", "X", "Y"], "x": [1, 2, 3]})
        folds = list(race_by_race_folds(df, race_col="gp"))
        assert len(folds) == 2

    def test_missing_race_col_raises(self):
        df = _frame(["A", "B"])
        with pytest.raises(ValueError, match="not in frame columns"):
            list(race_by_race_folds(df, race_col="nope"))
