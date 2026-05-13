"""Tests for aris.eval.scoring."""

import numpy as np
import pytest

from aris.eval.scoring import mae, per_race_mae, rmse


class TestMAE:
    def test_identical_returns_zero(self):
        y = np.array([1.0, 2.0, 3.0])
        assert mae(y, y) == 0.0

    def test_constant_offset(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([2.0, 3.0, 4.0])
        assert mae(y_true, y_pred) == pytest.approx(1.0)

    def test_mixed_residuals(self):
        y_true = np.array([10.0, 20.0, 30.0])
        y_pred = np.array([12.0, 18.0, 33.0])  # |2| + |-2| + |3| = 7; /3 = 7/3
        assert mae(y_true, y_pred) == pytest.approx(7.0 / 3.0)

    def test_accepts_lists(self):
        assert mae([1, 2, 3], [2, 3, 4]) == pytest.approx(1.0)

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="shape mismatch"):
            mae([1, 2, 3], [1, 2])

    def test_nan_in_true_raises(self):
        with pytest.raises(ValueError, match="NaN"):
            mae([1.0, np.nan, 3.0], [1.0, 2.0, 3.0])

    def test_nan_in_pred_raises(self):
        with pytest.raises(ValueError, match="NaN"):
            mae([1.0, 2.0, 3.0], [1.0, np.nan, 3.0])

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            mae([], [])


class TestRMSE:
    def test_identical_returns_zero(self):
        y = np.array([1.0, 2.0, 3.0])
        assert rmse(y, y) == 0.0

    def test_constant_offset(self):
        assert rmse([1.0, 2.0, 3.0], [2.0, 3.0, 4.0]) == pytest.approx(1.0)

    def test_rmse_ge_mae_with_outlier(self):
        y_true = np.array([0.0, 0.0, 0.0, 0.0])
        y_pred = np.array([0.0, 0.0, 0.0, 4.0])
        assert mae(y_true, y_pred) == pytest.approx(1.0)
        assert rmse(y_true, y_pred) == pytest.approx(2.0)


class TestPerRaceMAE:
    def test_returns_dict_keyed_by_race(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.5, 2.5, 3.5, 4.5])
        race_ids = np.array(["A", "A", "B", "B"])
        result = per_race_mae(y_true, y_pred, race_ids)
        assert isinstance(result, dict)
        assert set(result.keys()) == {"A", "B"}
        assert result["A"] == pytest.approx(0.5)
        assert result["B"] == pytest.approx(0.5)

    def test_different_per_race_values(self):
        y_true = np.array([1.0, 1.0, 5.0, 5.0])
        y_pred = np.array([1.0, 1.0, 5.5, 6.5])  # A: 0, B: 1.0
        race_ids = np.array(["A", "A", "B", "B"])
        result = per_race_mae(y_true, y_pred, race_ids)
        assert result["A"] == pytest.approx(0.0)
        assert result["B"] == pytest.approx(1.0)

    def test_race_ids_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="race_ids shape"):
            per_race_mae([1.0, 2.0], [1.0, 2.0], ["A"])

    def test_single_race(self):
        result = per_race_mae([1.0, 2.0], [2.0, 3.0], ["X", "X"])
        assert result == {"X": pytest.approx(1.0)}
