"""Track metadata loader — de-hardcode lap counts and pit loss."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from aris.physics.bicycle import Track, bahrain_2024

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

    def load_physics(self) -> Track:
        loader = _PHYSICS_LOADERS.get(self.physics_profile, bahrain_2024)
        track = loader()
        return Track(
            corners=track.corners,
            straight_length_m=track.straight_length_m,
            name=self.name,
            pit_loss_s=self.pit_loss_s,
        )


def _match_track_file(country: str) -> Path | None:
    needle = country.lower().replace(" ", "")
    for path in _TRACKS_DIR.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        aliases = {str(data.get("country", "")).lower().replace(" ", "")}
        aliases.add(path.stem.lower())
        for alias in data.get("round_aliases", []):
            aliases.add(str(alias).lower().replace(" ", ""))
        if needle in aliases:
            return path
    return None


@lru_cache(maxsize=16)
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
    return TrackConfig(
        name=str(data.get("name", country)),
        country=str(data.get("country", country)),
        total_laps=int(data.get("total_laps", 57)),
        pit_loss_s=float(data.get("pit_loss_s", 21.0)),
        physics_profile=str(data.get("physics_profile", "bahrain_2024")),
    )
