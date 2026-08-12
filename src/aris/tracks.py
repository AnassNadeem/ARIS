"""Track metadata loader — de-hardcode lap counts, pit loss, and geometry."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from aris.physics.bicycle import Corner, Track, bahrain_2024

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TRACKS_DIR = _REPO_ROOT / "data" / "tracks"

_PHYSICS_LOADERS = {
    "bahrain_2024": bahrain_2024,
}


@dataclass(frozen=True)
class TrackConfig:
    name: str
    country: str
    total_laps: int
    pit_loss_s: float
    physics_profile: str
    lap_length_m: float | None = None
    corners: tuple[Corner, ...] | None = None
    # Optional track-specific tyre deg slopes (s/lap of stint age). None → globals in tires.py.
    compound_slopes: dict[str, float] | None = None

    def load_physics(self) -> Track:
        """Build a bicycle ``Track``. Prefer YAML corners when present."""
        if self.corners:
            arc_total = sum(c.arc_length_m for c in self.corners)
            lap_length = self.lap_length_m if self.lap_length_m is not None else arc_total + 2000.0
            return Track(
                corners=self.corners,
                straight_length_m=max(0.0, lap_length - arc_total),
                name=self.name,
                pit_loss_s=self.pit_loss_s,
                compound_slopes=self.compound_slopes,
            )
        loader = _PHYSICS_LOADERS.get(self.physics_profile, bahrain_2024)
        track = loader()
        return Track(
            corners=track.corners,
            straight_length_m=track.straight_length_m,
            name=self.name,
            pit_loss_s=self.pit_loss_s,
            compound_slopes=self.compound_slopes,
        )


def _parse_corners(raw: object) -> tuple[Corner, ...] | None:
    if not raw:
        return None
    corners: list[Corner] = []
    for item in raw:  # type: ignore[union-attr]
        corners.append(
            Corner(
                radius_m=float(item["radius_m"]),
                arc_length_m=float(item["arc_length_m"]),
            )
        )
    return tuple(corners) if corners else None


def _normalize_token(value: str) -> str:
    return value.lower().replace(" ", "").replace("_", "").replace("-", "")


def _match_track_file(country: str) -> Path | None:
    """Resolve a track YAML for a GP/event/country needle.

    Prefer specific name/stem/round_aliases over country, because several
    circuits share a country (Italy, United States, Germany). Country is only
    used when exactly one config claims that country.
    """
    needle = _normalize_token(country)
    if not needle:
        return None

    specific_hits: list[Path] = []
    country_hits: list[Path] = []
    substring_hits: list[Path] = []

    for path in _TRACKS_DIR.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        specific = {_normalize_token(path.stem), _normalize_token(str(data.get("name", "")))}
        for alias in data.get("round_aliases", []):
            specific.add(_normalize_token(str(alias)))
        specific.discard("")
        country_alias = _normalize_token(str(data.get("country", "")))

        if needle in specific:
            specific_hits.append(path)
            continue
        # EventName like "Chinese Grand Prix" contains alias "chinese".
        if any(len(a) >= 4 and a in needle for a in specific):
            substring_hits.append(path)
            continue
        if country_alias and needle == country_alias:
            country_hits.append(path)

    if len(specific_hits) == 1:
        return specific_hits[0]
    if len(specific_hits) > 1:
        # Deterministic: prefer exact stem match if present.
        for path in specific_hits:
            if _normalize_token(path.stem) == needle:
                return path
        return sorted(specific_hits, key=lambda p: p.name)[0]
    if len(substring_hits) == 1:
        return substring_hits[0]
    if len(substring_hits) > 1:
        return sorted(substring_hits, key=lambda p: p.name)[0]
    if len(country_hits) == 1:
        return country_hits[0]
    return None


def _parse_compound_slopes(raw: object) -> dict[str, float] | None:
    """Optional YAML ``compound_slopes: {SOFT: 0.1, ...}`` → uppercase keys."""
    if not raw or not isinstance(raw, dict):
        return None
    out: dict[str, float] = {}
    for key, val in raw.items():
        if val is None:
            continue
        out[str(key).strip().upper()] = float(val)
    return out or None


def _config_from_data(country: str, data: dict) -> TrackConfig:
    return TrackConfig(
        name=str(data.get("name", country)),
        country=str(data.get("country", country)),
        total_laps=int(data.get("total_laps", 57)),
        pit_loss_s=float(data.get("pit_loss_s", 21.0)),
        physics_profile=str(data.get("physics_profile", "bahrain_2024")),
        lap_length_m=(
            float(data["lap_length_m"]) if data.get("lap_length_m") is not None else None
        ),
        corners=_parse_corners(data.get("corners")),
        compound_slopes=_parse_compound_slopes(data.get("compound_slopes")),
    )


@lru_cache(maxsize=32)
def load_track_config(country: str) -> TrackConfig:
    path = _match_track_file(country)
    if path is None:
        return TrackConfig(
            name=country,
            country=country,
            total_laps=57,
            pit_loss_s=21.0,
            physics_profile="bahrain_2024",
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _config_from_data(country, data)


def clear_track_config_cache() -> None:
    load_track_config.cache_clear()
