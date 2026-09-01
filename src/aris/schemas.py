"""Pydantic response models for T12 explainability endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StintMeta(BaseModel):
    stint_id: int
    compound: str
    start_lap: int
    end_lap: int


class DegradationCurveResponse(BaseModel):
    tyre_age: list[int]
    predicted_deg_s: list[float]
    actual_deg_s: list[float | None]
    lap_number: list[int] = Field(default_factory=list)
    compound: str
    circuit: str
    session_type: str
    session_id: str | None = None
    driver: str
    stint_id: int | None = None
    start_lap: int | None = None
    end_lap: int | None = None
    fresh_baseline_s: float | None = None
    available_stints: list[StintMeta] = Field(default_factory=list)


class GhostSeries(BaseModel):
    laps: list[int]
    position: list[int]
    gap_to_leader: list[float]
    compound: list[str]
    pit_laps: list[int]
    remaining_s: list[float] = Field(default_factory=list)


class GhostDeltaSeries(BaseModel):
    laps: list[int]
    position_delta: list[int]
    gap_delta: list[float]


class GhostVsRealResponse(BaseModel):
    session_id: str | None = None
    driver: str
    circuit: str | None = None
    ghost: GhostSeries
    real: GhostSeries
    delta: GhostDeltaSeries
    aris_action: str = ""
    explanation: str = ""


class TimelinePitStop(BaseModel):
    lap: int
    driver: str | None = None
    compound_in: str | None = None
    compound_out: str | None = None
    stint_length: int | None = None


class TimelinePeriod(BaseModel):
    kind: str
    start_lap: int
    end_lap: int


class DebriefTimeline(BaseModel):
    pit_stops: list[TimelinePitStop] = Field(default_factory=list)
    sc_vsc_periods: list[TimelinePeriod] = Field(default_factory=list)
    rain_periods: list[TimelinePeriod] = Field(default_factory=list)


class RecommendTop3Row(BaseModel):
    rank: int
    label: str
    delta_vs_stay_out_s: float | None = None
    p_best: float | None = None
    p10_delta_s: float | None = None
    p90_delta_s: float | None = None
    kind: str | None = None


class DebriefDecision(BaseModel):
    lap: int
    type: str
    recommend_top3: list[RecommendTop3Row] = Field(default_factory=list)
    chosen_action: str
    aris_action: str | None = None
    explanation: str = ""
    # Named driving factor (undercut / overcut / SC risk / tyre degradation)
    # behind this decision, derived from the recommendation's narration
    # context rather than the generic delta-vs-stay-out sentence above.
    why: str = ""


class DebriefMetadata(BaseModel):
    circuit: str
    season: int
    round_number: int
    total_laps: int
    session_id: str | None = None
    focus_driver: str | None = None
    session_type: str | None = None


class RaceDebriefResponse(BaseModel):
    timeline: DebriefTimeline
    decisions: list[DebriefDecision]
    metadata: DebriefMetadata
    extra: dict[str, Any] | None = None
