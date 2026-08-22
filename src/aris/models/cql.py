"""Conservative Q-learning scorer for strategy recommendations.

Torch is optional. Constants, state-vector construction, and the action
mapper import without it. Physics / CI paths must not require torch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from aris.state import RaceState

ACTION_STAY_OUT = 0
ACTION_PIT_SOFT = 1
ACTION_PIT_MEDIUM = 2
ACTION_PIT_HARD = 3
ACTION_PIT_INTER = 4
ACTION_PIT_WET = 5
STATE_DIM = 18
ACTION_DIM = 6

CONT_INDICES = [4, 5, 6, 7, 8, 9, 10, 14, 15, 16]

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = _REPO_ROOT / "models" / "cql_q_network.pt"
DEFAULT_NORM_PATH = _REPO_ROOT / "models" / "cql_normalisation.json"

_COMPOUND_INDEX = {
    "SOFT": 0,
    "MEDIUM": 1,
    "HARD": 2,
    "INTER": 3,
    "INTERMEDIATE": 3,
}
_PIT_COMPOUND_ACTION = {
    "SOFT": ACTION_PIT_SOFT,
    "MEDIUM": ACTION_PIT_MEDIUM,
    "HARD": ACTION_PIT_HARD,
    "INTER": ACTION_PIT_INTER,
    "INTERMEDIATE": ACTION_PIT_INTER,
    "WET": ACTION_PIT_WET,
}

_TORCH_OK: bool | None = None


def _torch_modules():
    """Lazy-import torch. Returns (torch, nn, F) or (None, None, None)."""
    global _TORCH_OK
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F

        _TORCH_OK = True
        return torch, nn, F
    except Exception:
        _TORCH_OK = False
        return None, None, None


def _clip(value: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, value)))


def raw_state_vector(state: RaceState) -> np.ndarray:
    """Un-normalised 18-feature vector (training + inference share this)."""
    x = np.zeros(STATE_DIM, dtype=np.float32)
    compound = str(state.compound or "").upper()
    idx = _COMPOUND_INDEX.get(compound)
    if idx is not None:
        x[idx] = 1.0

    tyre_life = float(state.tyre_life or 0)
    x[4] = _clip(tyre_life / 50.0, 0.0, 1.0)

    roll3 = state.stint_roll3
    lag1 = state.lag1_pace
    lag2 = state.lag2_pace
    if roll3 is not None and lag1 is not None:
        x[5] = _clip((float(lag1) - float(roll3)) / 3.0, -1.0, 1.0)
    if roll3 is not None and lag2 is not None:
        x[6] = _clip((float(lag2) - float(roll3)) / 3.0, -1.0, 1.0)

    gap = state.gap_ahead_s
    gap_v = 22.0 if gap is None else float(gap)
    x[7] = min(gap_v, 22.0) / 22.0

    hist = [float(g) for g in (state.gap_ahead_history or [])]
    if len(hist) >= 3:
        last3 = hist[-3:]
        diffs = [last3[i + 1] - last3[i] for i in range(len(last3) - 1)]
        x[8] = _clip(float(np.mean(diffs)) / 0.5, -1.0, 1.0)
        x[17] = _clip((hist[-1] - hist[-3]) / 1.0, -1.0, 1.0)

    x[9] = float(state.fuel_kg or 0.0) / 110.0

    total = int(state.total_laps or 0)
    lap = int(state.lap_number or 0)
    remaining = total - lap if total else int(state.laps_remaining or 0)
    x[10] = float(remaining) / 72.0

    status = str(state.track_status or "").strip()
    x[11] = 1.0 if status in {"4", "6"} else 0.0
    x[12] = 1.0 if status == "1" else 0.0
    x[13] = 1.0 if bool(state.rainfall) else 0.0

    if state.position is None:
        x[14] = 0.5
    else:
        x[14] = float(state.position) / 20.0

    stint = int(getattr(state, "stint_number", 1) or 1)
    x[15] = min(stint, 3) / 3.0
    x[16] = (float(lap) / float(total)) if total else 0.0
    return x


def build_state_vector(
    state: RaceState,
    normalisation: dict,
) -> np.ndarray:
    """Build normalised 18-feature state vector."""
    x = raw_state_vector(state)
    if not normalisation:
        return x
    indices = normalisation.get("cont_indices", CONT_INDICES)
    means = normalisation.get("means") or []
    stds = normalisation.get("stds") or []
    for i, mean, std in zip(indices, means, stds, strict=False):
        ii = int(i)
        if 0 <= ii < STATE_DIM:
            x[ii] = _clip((float(x[ii]) - float(mean)) / (float(std) + 1e-8), -3.0, 3.0)
    return x


def map_recommendation_to_action(rec) -> int | None:
    """Map a Recommendation (or StrategyAction) to one of 6 action indices."""
    action = getattr(rec, "action", rec)
    kind = getattr(action, "kind", action)
    kind_s = str(getattr(kind, "value", kind) or "").upper().replace("ACTIONKIND.", "")
    label = (
        getattr(action, "label_override", None)
        or getattr(rec, "label", None)
        or ""
    )
    label_s = str(label).upper()

    pit_laps = getattr(action, "pit_laps", None)
    pit_compounds = getattr(action, "pit_compounds", None)
    if kind_s in {"STAY_OUT", "LIFT", "BRAKE"}:
        if pit_laps and pit_compounds:
            return _PIT_COMPOUND_ACTION.get(str(pit_compounds[0]).upper())
        return ACTION_STAY_OUT

    is_pit = kind_s in {"PIT", "PIT_SOON", "PIT_LAP", "PIT_NOW"} or "OVERCUT" in label_s
    if is_pit:
        compound = getattr(action, "pit_compound", None)
        if compound is None:
            return None
        return _PIT_COMPOUND_ACTION.get(str(compound).upper())
    return None


def _qnetwork_class():
    torch, nn, F = _torch_modules()
    if nn is None:
        return None

    class QNetwork(nn.Module):
        def __init__(self, state_dim=STATE_DIM, action_dim=ACTION_DIM, hidden=128):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(state_dim, hidden),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(hidden, hidden),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(hidden, action_dim),
            )

        def forward(self, x):
            return self.net(x)

    return QNetwork


QNetwork = _qnetwork_class()


def cql_loss(q_net, states, actions, returns, gamma=0.95, alpha=1.0):
    """MC Bellman + CQL penalty. No s' bootstrapping."""
    del gamma
    torch, _nn, F = _torch_modules()
    if torch is None or F is None:
        raise ImportError("torch is required for cql_loss")
    q_all = q_net(states)
    q_taken = q_all.gather(1, actions.unsqueeze(1)).squeeze(1)
    bellman = F.mse_loss(q_taken, returns)
    cql_pen = (torch.logsumexp(q_all, dim=1) - q_taken).mean()
    return bellman + alpha * cql_pen


def cql_score_candidates(
    state: RaceState,
    recommendations: list,
    q_net: Any,
    normalisation: dict,
) -> list:
    """Set cql_q_delta on each recommendation. Does not re-order."""
    torch, _nn, _F = _torch_modules()
    if torch is None or q_net is None:
        for rec in recommendations:
            rec.cql_q_delta = 0.0
        return recommendations
    vec = build_state_vector(state, normalisation)
    x = torch.tensor(vec, dtype=torch.float32).unsqueeze(0)
    q_net.eval()
    with torch.no_grad():
        q_all = q_net(x).squeeze(0)
        q_stay = float(q_all[ACTION_STAY_OUT].item())
        for rec in recommendations:
            action_idx = map_recommendation_to_action(rec)
            if action_idx is None:
                rec.cql_q_delta = 0.0
            else:
                rec.cql_q_delta = float(q_all[int(action_idx)].item()) - q_stay
    return recommendations


def load_cql_model(
    model_path: str | Path = "models/cql_q_network.pt",
    norm_path: str | Path = "models/cql_normalisation.json",
) -> tuple[Any, dict] | tuple[None, None]:
    """Load Q-network and normalisation. Never raises."""
    try:
        torch, _nn, _F = _torch_modules()
        if torch is None:
            return None, None
        model_p = Path(model_path)
        norm_p = Path(norm_path)
        if not model_p.is_absolute():
            model_p = _REPO_ROOT / model_p
        if not norm_p.is_absolute():
            norm_p = _REPO_ROOT / norm_p
        if not model_p.exists() or not norm_p.exists():
            return None, None
        normalisation = json.loads(norm_p.read_text(encoding="utf-8"))
        cls = _qnetwork_class()
        if cls is None:
            return None, None
        hidden = int(normalisation.get("hidden", 128))
        q_net = cls(hidden=hidden)
        state = torch.load(model_p, map_location="cpu", weights_only=True)
        q_net.load_state_dict(state)
        q_net.eval()
        return q_net, normalisation
    except Exception:
        return None, None
