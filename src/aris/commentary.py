"""Rule-based field intelligence — observes, never recommends strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aris.field.rivals import RivalPitEstimate, RivalState, estimate_rival_pit_lap
from aris.physics.tires import normalize_compound
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
    rainfall: bool = False

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


_COMPOUND_SHORT = {
    "SOFT": "SOFT",
    "MEDIUM": "MED",
    "HARD": "HARD",
    "INTERMEDIATE": "INTER",
    "WET": "WET",
}
FIELD_BOARD_INTERVAL = 10


def _rival_states_from_snapshot(
    snap: FieldSnapshot,
    focus_driver: str,
) -> list[RivalState]:
    focus = (focus_driver or "").upper()
    ours = snap.get_driver(focus)
    focus_gap = float(ours.gap_to_leader_s) if ours and ours.gap_to_leader_s is not None else 0.0
    ordered = sorted(
        (d for d in snap.drivers if d.position is not None),
        key=lambda d: int(d.position or 99),
    )
    out: list[RivalState] = []
    for drv in ordered:
        code = (drv.code or "").upper()
        if not code or code == focus:
            continue
        gap = focus_gap - float(drv.gap_to_leader_s or 0.0)
        out.append(
            RivalState(
                driver_code=code,
                position=int(drv.position or 99),
                compound=normalize_compound(drv.compound),
                tyre_life=int(drv.tyre_life) if drv.tyre_life is not None else 1,
                gap_to_focus=gap,
                gap_trend=0.0,
                team="",
                last_lap_s=(drv.last_lap_ms / 1000.0) if drv.last_lap_ms else 0.0,
                stint_number=int(drv.stint_number or 1),
            )
        )
        if len(out) >= 6:
            break
    return out


def estimates_from_snapshot(
    snap: FieldSnapshot,
    focus_driver: str,
    *,
    circuit_key: str = "",
) -> list[RivalPitEstimate]:
    rivals = _rival_states_from_snapshot(snap, focus_driver)
    estimates = [
        estimate_rival_pit_lap(
            rival,
            snap.lap,
            snap.total_laps,
            circuit_key,
        )
        for rival in rivals
    ]
    return sorted(estimates, key=lambda e: (e.estimated_pit_lap, e.driver_code))


def generate_field_strategy_board(
    rivals: list[RivalPitEstimate],
    focus_driver: str,
    current_lap: int,
    total_laps: int,
    *,
    stint_by_code: dict[str, int] | None = None,
) -> CommentaryMessage | None:
    """Plain-text FIELD board for the comms panel. Top 6, exclude focus."""
    del current_lap, total_laps
    focus = (focus_driver or "").upper()
    stints = stint_by_code or {}
    parts: list[str] = []
    for est in rivals:
        if est.driver_code.upper() == focus:
            continue
        short = _COMPOUND_SHORT.get(est.compound, est.compound[:3])
        already = int(stints.get(est.driver_code, 1)) >= 2
        if already:
            parts.append(
                f"{est.driver_code} already pitted ({short} {est.tyre_life}L)"
            )
            continue
        if est.confidence == "HIGH":
            box = f"box L{est.estimated_pit_lap}"
        elif est.confidence == "LOW":
            box = f"est. box L{est.estimated_pit_lap}"
        else:
            box = f"box ~L{est.estimated_pit_lap}"
        parts.append(f"{est.driver_code} {box} ({short} {est.tyre_life}L)")
    if not parts:
        return None
    return CommentaryMessage(type="FIELD", text="FIELD: " + " · ".join(parts))


def _estimates_shifted(
    prev: dict[str, int],
    current: list[RivalPitEstimate],
) -> bool:
    for est in current:
        old = prev.get(est.driver_code)
        if old is not None and abs(est.estimated_pit_lap - old) > 3:
            return True
    return False


class CommentaryEngine:
    def __init__(self) -> None:
        self.prev_field: FieldSnapshot | None = None
        self.prev_fastest_lap_holder: str | None = None
        self.announced_milestones: set[int] = set()
        self.announced_approach: set[float] = set()
        self.last_track_status: str = "1"
        self.last_field_board_lap: int | None = None
        self.last_estimates: dict[str, int] = {}
        self.overcut_hold_laps: dict[str, int] = {}

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
        focus = (focus_driver or "").upper()
        prior_estimates = dict(self.last_estimates)
        estimates = estimates_from_snapshot(current_field, focus_driver)
        board_due = (
            lap == 1
            or (lap % FIELD_BOARD_INTERVAL == 0)
            or _estimates_shifted(self.last_estimates, estimates)
        )
        if board_due and estimates:
            stints = {
                d.code.upper(): int(d.stint_number or 1)
                for d in current_field.drivers
                if d.code
            }
            board = generate_field_strategy_board(
                estimates, focus_driver, lap, total_laps, stint_by_code=stints
            )
            if board is not None:
                messages.append(board)
                self.last_field_board_lap = lap
                self.last_estimates = {e.driver_code: e.estimated_pit_lap for e in estimates}

        if self.prev_field is None:
            self.prev_field = current_field
            self.prev_fastest_lap_holder = current_field.fastest_lap_holder()
            return messages

        # Observed rainfall only — never track_status 4 (Safety Car).
        if current_field.rainfall and not self.prev_field.rainfall:
            messages.append(
                CommentaryMessage(
                    type="ALERT",
                    text=(
                        "RAIN DETECTED. Track conditions changing. "
                        "Intermediate window opening if conditions worsen. "
                        "[WET HEURISTIC — reduced confidence]"
                    ),
                )
            )
        if (not current_field.rainfall) and self.prev_field.rainfall:
            messages.append(
                CommentaryMessage(
                    type="INFO",
                    text=(
                        "Rain easing. Track drying. Monitor conditions "
                        "for slick window. Intermediates may begin graining."
                    ),
                )
            )
        focus_wet = current_field.get_driver(focus) if focus else None
        focus_compound = normalize_compound(focus_wet.compound if focus_wet else None)
        remaining_now = total_laps - lap
        if (
            current_field.rainfall
            and focus_compound in {"INTERMEDIATE", "INTER", "WET"}
            and remaining_now > 10
            and lap % 5 == 0
        ):
            hold = "INTER" if focus_compound in {"INTERMEDIATE", "INTER"} else "WET"
            messages.append(
                CommentaryMessage(
                    type="INFO",
                    text=(
                        f"Conditions still wet. Hold {hold}. "
                        f"{remaining_now} laps remaining. "
                        "Monitor for dry window."
                    ),
                )
            )

        for drv in current_field.drivers:
            prev = self.prev_field.get_driver(drv.code)
            if prev and drv.stint_number is not None and prev.stint_number is not None:
                if drv.stint_number > prev.stint_number:
                    hold = self.overcut_hold_laps.get(drv.code.upper())
                    est_lap = prior_estimates.get(drv.code.upper())
                    in_window = hold is not None and lap <= hold
                    if not in_window and est_lap is not None:
                        in_window = 0 <= int(est_lap) - (lap - 1) <= 8
                    remaining = total_laps - lap
                    gap_ok = True
                    ours = current_field.get_driver(focus) if focus else None
                    if ours and ours.gap_to_leader_s is not None and drv.gap_to_leader_s is not None:
                        gap_ok = abs(float(drv.gap_to_leader_s) - float(ours.gap_to_leader_s)) >= 2.0
                    if (
                        drv.code.upper() != focus
                        and in_window
                        and remaining >= 15
                        and gap_ok
                    ):
                        n = (hold - lap) if hold is not None else 4
                        messages.append(
                            CommentaryMessage(
                                type="INTEL",
                                text=(
                                    f"OVERCUT ACTIVE — {drv.code} pitted. "
                                    f"Hold {max(int(n), 0)} more laps."
                                ),
                            )
                        )
                    else:
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
