"""Rule-based field intelligence — observes, never recommends strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aris.simulate import get_pit_loss


@dataclass
class CommentaryMessage:
    type: str
    text: str


def _sc_pit_window_text(
    pit_loss_s: float | None,
    *,
    track_status: str,
    virtual: bool = False,
) -> str:
    if pit_loss_s is None or pit_loss_s <= 0:
        if virtual:
            return "VIRTUAL SAFETY CAR. Hold position."
        return "SAFETY CAR DEPLOYED. Pit window opens."
    effective = get_pit_loss(float(pit_loss_s), track_status)
    if virtual:
        return (
            f"VSC deployed. Pit loss now ~{effective:.0f}s. "
            f"Window open if gap to pit exit > {effective:.0f}s."
        )
    return (
        f"SC deployed. Pit loss now ~{effective:.0f}s. "
        f"Window open if gap to pit exit > {effective:.0f}s."
    )


@dataclass
class DriverSnap:
    code: str
    position: int | None = None
    gap_to_leader_s: float | None = None
    gap_ahead_s: float | None = None
    compound: str | None = None
    tyre_life: int | None = None
    stint_number: int | None = None
    last_lap_ms: int | None = None
    best_lap_ms: int | None = None


@dataclass
class FieldSnapshot:
    lap: int
    total_laps: int
    drivers: list[DriverSnap] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)

    def get_driver(self, code: str) -> DriverSnap | None:
        needle = code.upper()
        for drv in self.drivers:
            if drv.code.upper() == needle:
                return drv
        return None

    def driver_at_position(self, position: int) -> DriverSnap | None:
        for drv in self.drivers:
            if drv.position == position:
                return drv
        return None

    def car_directly_ahead(self, focus: str) -> DriverSnap | None:
        mine = self.get_driver(focus)
        if mine is None or mine.position is None or mine.position <= 1:
            return None
        return self.driver_at_position(mine.position - 1)

    def car_directly_behind(self, focus: str) -> DriverSnap | None:
        mine = self.get_driver(focus)
        if mine is None or mine.position is None:
            return None
        return self.driver_at_position(mine.position + 1)

    def fastest_lap_holder(self) -> str | None:
        best: tuple[str, int] | None = None
        for drv in self.drivers:
            if drv.best_lap_ms is None:
                continue
            if best is None or drv.best_lap_ms < best[1]:
                best = (drv.code, drv.best_lap_ms)
        return best[0] if best else None

    def fastest_lap_time_s(self) -> float | None:
        times = [d.best_lap_ms for d in self.drivers if d.best_lap_ms]
        if not times:
            return None
        return min(times) / 1000.0


class CommentaryEngine:
    def __init__(self) -> None:
        self.prev_field: FieldSnapshot | None = None
        self.prev_fastest_lap_holder: str | None = None
        self.announced_milestones: set[int] = set()
        self.announced_approach: set[float] = set()
        self.last_track_status: str = "1"

    def generate(
        self,
        current_field: FieldSnapshot,
        focus_driver: str,
        lap: int,
        total_laps: int,
        race_control_messages: list[dict[str, Any]] | None = None,
        *,
        pit_loss_s: float | None = None,
        deg_rate_s: float | None = None,
    ) -> list[CommentaryMessage]:
        messages: list[CommentaryMessage] = []
        rc = race_control_messages if race_control_messages is not None else current_field.messages
        if self.prev_field is None:
            self.prev_field = current_field
            self.prev_fastest_lap_holder = current_field.fastest_lap_holder()
            return messages

        focus = (focus_driver or "").upper()

        for drv in current_field.drivers:
            prev = self.prev_field.get_driver(drv.code)
            if prev and drv.stint_number is not None and prev.stint_number is not None:
                if drv.stint_number > prev.stint_number:
                    msg = (
                        f"{drv.code} has pitted — now on "
                        f"{drv.compound or 'fresh tyres'}. Emerged P{drv.position}"
                    )
                    if drv.code != focus and focus:
                        ours = current_field.get_driver(focus)
                        if ours and ours.gap_to_leader_s is not None and drv.gap_to_leader_s is not None:
                            gap = drv.gap_to_leader_s - ours.gap_to_leader_s
                            msg += f", {gap:+.1f}s to us"
                    messages.append(CommentaryMessage(type="INTEL", text=msg + "."))

        fl_holder = current_field.fastest_lap_holder()
        if fl_holder and fl_holder != self.prev_fastest_lap_holder:
            fl_time = current_field.fastest_lap_time_s()
            if fl_time is not None:
                messages.append(
                    CommentaryMessage(type="INFO", text=f"{fl_holder} sets fastest lap — {fl_time:.3f}s.")
                )
            self.prev_fastest_lap_holder = fl_holder

        car_behind = current_field.car_directly_behind(focus) if focus else None
        if car_behind and car_behind.gap_ahead_s is not None:
            if car_behind.gap_ahead_s < 1.5:
                messages.append(
                    CommentaryMessage(
                        type="ALERT",
                        text=(
                            f"{car_behind.code} closing — {car_behind.gap_ahead_s:.1f}s "
                            "behind. Undercut window opening."
                        ),
                    )
                )
            elif car_behind.gap_ahead_s < 3.0:
                messages.append(
                    CommentaryMessage(
                        type="ALERT",
                        text=f"{car_behind.code} in mirror — {car_behind.gap_ahead_s:.1f}s.",
                    )
                )

        car_ahead = current_field.car_directly_ahead(focus) if focus else None
        if car_ahead and car_ahead.gap_ahead_s is not None:
            prev_ahead = self.prev_field.car_directly_ahead(focus)
            if prev_ahead and prev_ahead.gap_ahead_s is not None:
                delta = car_ahead.gap_ahead_s - prev_ahead.gap_ahead_s
                if abs(delta) > 0.3:
                    direction = "opening" if delta > 0 else "closing"
                    messages.append(
                        CommentaryMessage(
                            type="INFO",
                            text=(
                                f"Gap to {car_ahead.code} {direction} — "
                                f"now {car_ahead.gap_ahead_s:.1f}s."
                            ),
                        )
                    )

        for rc_msg in rc:
            blob = f"{rc_msg.get('flag') or ''} {rc_msg.get('category') or ''} {rc_msg.get('message') or ''}".upper()
            if "SAFETY CAR" in blob or rc_msg.get("flag") == "SC":
                messages.append(
                    CommentaryMessage(
                        type="ALERT",
                        text=_sc_pit_window_text(pit_loss_s, track_status="4"),
                    )
                )
            elif "VIRTUAL" in blob or rc_msg.get("flag") == "VSC":
                messages.append(
                    CommentaryMessage(
                        type="ALERT",
                        text=_sc_pit_window_text(pit_loss_s, track_status="6", virtual=True),
                    )
                )
            elif "CLEAR" in blob or rc_msg.get("flag") == "GREEN":
                messages.append(CommentaryMessage(type="INFO", text="Track is green. Normal racing resumes."))

        remaining = total_laps - lap
        for m in (20, 10, 5, 3, 1):
            if remaining == m and m not in self.announced_milestones:
                self.announced_milestones.add(m)
                messages.append(CommentaryMessage(type="INFO", text=f"{m} laps remaining."))

        focus_snap = current_field.get_driver(focus) if focus else None
        if focus_snap is not None and focus_snap.tyre_life is not None:
            rate = float(deg_rate_s) if deg_rate_s is not None else 0.05
            for frac in (0.25, 0.50, 0.75):
                threshold_laps = int(frac * total_laps)
                if (
                    threshold_laps - 5 <= focus_snap.tyre_life < threshold_laps
                    and frac not in self.announced_approach
                ):
                    self.announced_approach.add(frac)
                    n = threshold_laps - focus_snap.tyre_life
                    messages.append(
                        CommentaryMessage(
                            type="INFO",
                            text=(
                                f"Pit window opens in ~{n} laps. "
                                f"Current deg rate {rate:.3f}s/lap."
                            ),
                        )
                    )

        self.prev_field = current_field
        return messages


def events_for_transition(
    prev: FieldSnapshot | None,
    current: FieldSnapshot,
    focus_driver: str,
    *,
    pit_loss_s: float | None = None,
    deg_rate_s: float | None = None,
) -> list[CommentaryMessage]:
    engine = CommentaryEngine()
    engine.prev_field = prev
    if prev is not None:
        engine.prev_fastest_lap_holder = prev.fastest_lap_holder()
    remaining = current.total_laps - current.lap
    engine.announced_milestones = {m for m in (20, 10, 5, 3, 1) if remaining < m}
    focus = (focus_driver or "").upper()
    snap = current.get_driver(focus) if focus else None
    if snap is not None and snap.tyre_life is not None:
        engine.announced_approach = {
            frac
            for frac in (0.25, 0.50, 0.75)
            if snap.tyre_life > int(frac * current.total_laps) - 5
        }
    return engine.generate(
        current,
        focus_driver,
        current.lap,
        current.total_laps,
        current.messages,
        pit_loss_s=pit_loss_s,
        deg_rate_s=deg_rate_s,
    )
