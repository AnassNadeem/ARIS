#!/usr/bin/env python
"""Audit R2 race_field.json against FastF1 for DNF/DNS, SC/VSC/red, and wet flags.

    python scripts/audit_race_accuracy.py
    python scripts/audit_race_accuracy.py --year 2025 --round 1
    python scripts/audit_race_accuracy.py --json-out results/race_accuracy_audit.json

Report only — does not rewrite race_field.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_REPLAY = ROOT / "data" / "replay_r2" / "replay"
FIELDS = ("dnf", "dns", "sc", "vsc", "red", "wet")

_log = logging.getLogger("aris.audit_accuracy")

DNS_TOKENS = ("DID NOT START", "DID NOT QUALIFY", "DNS", "DNQ")
FINISHED_EXACT = frozenset({"", "FINISHED", "FINISHED LAP"})


@dataclass(frozen=True)
class Period:
    start: int
    end: int
    extra: str | None = None

    def key(self) -> tuple[int, int]:
        return (self.start, self.end)

    def label(self) -> str:
        core = f"{self.start}-{self.end}" if self.start != self.end else str(self.start)
        return f"{core}:{self.extra}" if self.extra else core


@dataclass
class RaceFacts:
    year: int
    round: int
    circuit: str = ""
    dnf: list[tuple[str, int]] = field(default_factory=list)
    dns: list[str] = field(default_factory=list)
    sc: list[Period] = field(default_factory=list)
    vsc: list[Period] = field(default_factory=list)
    red: list[Period] = field(default_factory=list)
    wet_laps: list[int] = field(default_factory=list)
    wet_ever: bool = False
    race_control_n: int = 0
    notes: list[str] = field(default_factory=list)


def _is_classified_position(classified: Any) -> bool:
    if classified is None:
        return False
    text = str(classified).strip().upper()
    if not text or text in {"R", "D", "W", "NC", "NAN", "NONE"}:
        return False
    try:
        int(float(classified))
        return True
    except (TypeError, ValueError):
        return False


def _status_kind(status: str, lap_count: int, classified: Any = None) -> str:
    u = (status or "").strip().upper()
    classed = str(classified if classified is not None else "").strip().upper()
    # FastF1 3.x uses "Lapped" for +N classified finishers, not "+1 Lap".
    finished = (
        _is_classified_position(classified)
        or u in FINISHED_EXACT
        or u.startswith("+")
        or u == "LAPPED"
    )
    if finished:
        return "finished"
    if " LAP" in u and (u[0].isdigit() or u.startswith("+")):
        return "finished"
    if any(tok in u for tok in DNS_TOKENS) or classed == "W":
        return "dns"
    if "DISQUAL" in u or u == "DSQ" or classed == "D":
        return "dsq"
    if lap_count < 1 and any(tok in u for tok in DNS_TOKENS):
        return "dns"
    return "dnf"


def _flag_from_track_status(status: str | None) -> str:
    s = str(status or "").strip()
    if not s or s in {"None", "nan"}:
        return "GREEN"
    if "5" in s:
        return "RED"
    if "4" in s:
        return "SC"
    if "6" in s or "7" in s:
        return "VSC"
    return "GREEN"


def merge_runs(laps: list[int]) -> list[Period]:
    nums = sorted({int(n) for n in laps if int(n) >= 1})
    if not nums:
        return []
    out: list[Period] = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append(Period(start, prev))
        start = prev = n
    out.append(Period(start, prev))
    return out


def _most_severe_by_lap(rows: list[dict[str, Any]]) -> dict[int, str]:
    rank = {"GREEN": 0, "VSC": 1, "SC": 2, "RED": 3}
    best: dict[int, str] = {}
    for row in rows:
        try:
            lap = int(row["lap"])
        except (TypeError, ValueError, KeyError):
            continue
        if lap < 1:
            continue
        flag = _flag_from_track_status(row.get("track_status"))
        if rank[flag] > rank.get(best.get(lap, "GREEN"), 0):
            best[lap] = flag
    return best


def periods_from_track_rows(rows: list[dict[str, Any]]) -> dict[str, list[Period]]:
    by_lap = _most_severe_by_lap(rows)
    buckets = {"SC": [], "VSC": [], "RED": []}
    for lap, flag in by_lap.items():
        if flag in buckets:
            buckets[flag].append(lap)
    return {kind: merge_runs(laps) for kind, laps in buckets.items()}


def _restart_type(messages: list[dict[str, Any]], red: Period) -> str:
    blobs: list[str] = []
    for msg in messages:
        lap = msg.get("lap")
        try:
            lap_n = int(lap) if lap is not None else None
        except (TypeError, ValueError):
            lap_n = None
        if lap_n is not None and lap_n < red.start:
            continue
        flag = msg.get("flag") or ""
        message = msg.get("message") or ""
        category = msg.get("category") or ""
        blob = f"{flag} {message} {category}".upper()
        blobs.append(blob)
    joined = " ".join(blobs)
    if "STANDING START" in joined:
        return "standing"
    if "ROLLING START" in joined:
        return "rolling"
    if "SAFETY CAR IN THIS LAP" in joined or "SAFETY CAR" in joined:
        return "rolling"
    return "unknown"


def attach_red_restarts(red: list[Period], messages: list[dict[str, Any]]) -> list[Period]:
    if not red:
        return []
    return [Period(p.start, p.end, _restart_type(messages, p)) for p in red]


def facts_from_field(payload: dict[str, Any]) -> RaceFacts:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    year = int(meta.get("year") or 0)
    rnd = int(meta.get("round") or 0)
    circuit = str(meta.get("circuit_name") or "")
    laps = payload.get("laps") if isinstance(payload.get("laps"), list) else []
    drivers = payload.get("drivers") if isinstance(payload.get("drivers"), list) else []
    weather = payload.get("weather") if isinstance(payload.get("weather"), list) else []
    rc = payload.get("race_control") if isinstance(payload.get("race_control"), list) else []

    last_lap: dict[str, int] = {}
    dnf: list[tuple[str, int]] = []
    for row in laps:
        code = str(row.get("driver") or "")
        try:
            lap_n = int(row.get("lap") or 0)
        except (TypeError, ValueError):
            continue
        if not code or lap_n < 1:
            continue
        last_lap[code] = max(last_lap.get(code, 0), lap_n)
        if row.get("is_dnf"):
            dnf.append((code, lap_n))
    dnf = sorted({(c, n) for c, n in dnf})
    listed = [str(d.get("code") or "") for d in drivers if d.get("code")]
    dns = sorted({c for c in listed if c and last_lap.get(c, 0) < 1})

    periods = periods_from_track_rows(laps)
    rc_msgs = [
        {
            "lap": m.get("lap"),
            "message": m.get("message"),
            "flag": m.get("flag"),
            "category": m.get("category"),
        }
        for m in rc
        if isinstance(m, dict)
    ]
    red = attach_red_restarts(periods["RED"], rc_msgs)
    wet_laps = sorted(
        {
            int(w["lap"])
            for w in weather
            if isinstance(w, dict) and w.get("rainfall") and int(w.get("lap") or 0) >= 1
        }
    )
    notes: list[str] = []
    if not rc_msgs:
        notes.append("race_control_empty")
    return RaceFacts(
        year=year,
        round=rnd,
        circuit=circuit,
        dnf=dnf,
        dns=dns,
        sc=periods["SC"],
        vsc=periods["VSC"],
        red=red,
        wet_laps=wet_laps,
        wet_ever=bool(wet_laps),
        race_control_n=len(rc_msgs),
        notes=notes,
    )


def facts_from_session(sess: Any, year: int, round_number: int, circuit: str = "") -> RaceFacts:
    import pandas as pd

    from aris.physics.wet import nearest_rainfall

    results = getattr(sess, "results", None)
    laps = getattr(sess, "laps", None)
    last_lap: dict[str, int] = {}
    track_rows: list[dict[str, Any]] = []
    if laps is not None and not getattr(laps, "empty", True):
        for rec in laps.itertuples(index=False):
            code = str(getattr(rec, "Driver", "") or "")
            try:
                lap_n = int(getattr(rec, "LapNumber", 0) or 0)
            except (TypeError, ValueError):
                continue
            if not code or lap_n < 1:
                continue
            last_lap[code] = max(last_lap.get(code, 0), lap_n)
            status = getattr(rec, "TrackStatus", None)
            try:
                track = None if status is None or pd.isna(status) else str(status)
            except (TypeError, ValueError):
                track = str(status) if status is not None else None
            track_rows.append({"lap": lap_n, "track_status": track, "driver": code})

    dnf: list[tuple[str, int]] = []
    dns: list[str] = []
    if results is not None and not getattr(results, "empty", True):
        for rec in results.itertuples(index=False):
            code = str(getattr(rec, "Abbreviation", "") or "")
            if not code:
                continue
            status = str(getattr(rec, "Status", "") or "")
            classified = getattr(rec, "ClassifiedPosition", None)
            n_laps = last_lap.get(code, 0)
            kind = _status_kind(status, n_laps, classified)
            if kind == "dns":
                dns.append(code)
            elif kind in {"dnf", "dsq"}:
                retire_lap = n_laps if n_laps >= 1 else 1
                dnf.append((code, retire_lap))
    dns = sorted(set(dns))
    dnf = sorted({(c, n) for c, n in dnf})

    periods = periods_from_track_rows(track_rows)
    rc_raw = getattr(sess, "race_control_messages", None)
    if rc_raw is None:
        rc_raw = getattr(sess, "messages", None)
    rc_msgs: list[dict[str, Any]] = []
    if rc_raw is not None and not getattr(rc_raw, "empty", True):
        for rec in rc_raw.itertuples(index=False):
            lap_v = getattr(rec, "Lap", None)
            try:
                lap_n = None if lap_v is None or pd.isna(lap_v) else int(lap_v)
            except (TypeError, ValueError):
                lap_n = None
            rc_msgs.append(
                {
                    "lap": lap_n,
                    "message": str(getattr(rec, "Message", "") or ""),
                    "flag": None
                    if getattr(rec, "Flag", None) is None
                    else str(getattr(rec, "Flag", "")),
                    "category": None
                    if getattr(rec, "Category", None) is None
                    else str(getattr(rec, "Category", "")),
                }
            )
    red = attach_red_restarts(periods["RED"], rc_msgs)

    wet_laps: list[int] = []
    weather = getattr(sess, "weather_data", None)
    if laps is not None and not getattr(laps, "empty", True) and "LapNumber" in laps.columns:
        total = int(laps["LapNumber"].max() or 0)
        starts = None
        if "LapStartTime" in laps.columns:
            starts = laps.dropna(subset=["LapStartTime"]).sort_values("LapNumber")
        for lap_n in range(1, total + 1):
            start = None
            if starts is not None:
                hit = starts[starts["LapNumber"] == lap_n]
                if not hit.empty:
                    start = hit["LapStartTime"].iloc[0]
            if nearest_rainfall(weather, start):
                wet_laps.append(lap_n)

    notes: list[str] = []
    if rc_msgs:
        notes.append(f"ff1_race_control_n={len(rc_msgs)}")
    else:
        notes.append("ff1_race_control_empty")
    return RaceFacts(
        year=int(year),
        round=int(round_number),
        circuit=circuit,
        dnf=sorted({(c, n) for c, n in dnf}),
        dns=dns,
        sc=periods["SC"],
        vsc=periods["VSC"],
        red=red,
        wet_laps=wet_laps,
        wet_ever=bool(wet_laps),
        race_control_n=len(rc_msgs),
        notes=notes,
    )


def _fmt_dnf(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return "—"
    return ", ".join(f"{c}@{n}" for c, n in rows)


def _fmt_periods(rows: list[Period]) -> str:
    if not rows:
        return "—"
    return ", ".join(p.label() for p in rows)


def compare_field(name: str, aris: RaceFacts, ff1: RaceFacts) -> dict[str, Any]:
    if name == "dnf":
        a, b = set(aris.dnf), set(ff1.dnf)
        status = "pass" if a == b else "mismatch"
        return {
            "status": status,
            "aris": _fmt_dnf(aris.dnf),
            "fastf1": _fmt_dnf(ff1.dnf),
            "aris_only": _fmt_dnf(sorted(a - b)),
            "ff1_only": _fmt_dnf(sorted(b - a)),
        }
    if name == "dns":
        a, b = set(aris.dns), set(ff1.dns)
        status = "pass" if a == b else "mismatch"
        return {
            "status": status,
            "aris": ", ".join(aris.dns) or "—",
            "fastf1": ", ".join(ff1.dns) or "—",
            "aris_only": ", ".join(sorted(a - b)) or "—",
            "ff1_only": ", ".join(sorted(b - a)) or "—",
        }
    if name in {"sc", "vsc"}:
        a = [p.key() for p in getattr(aris, name)]
        b = [p.key() for p in getattr(ff1, name)]
        status = "pass" if a == b else "mismatch"
        return {
            "status": status,
            "aris": _fmt_periods(getattr(aris, name)),
            "fastf1": _fmt_periods(getattr(ff1, name)),
        }
    if name == "red":
        a_keys = [p.key() for p in aris.red]
        b_keys = [p.key() for p in ff1.red]
        a_extra = [p.extra or "unknown" for p in aris.red]
        b_extra = [p.extra or "unknown" for p in ff1.red]
        periods_ok = a_keys == b_keys
        restart_ok = (not b_keys) or (a_extra == b_extra)
        status = "pass" if (periods_ok and restart_ok) else "mismatch"
        detail = []
        if not periods_ok:
            detail.append("periods")
        if periods_ok and not restart_ok:
            detail.append("restart_type")
        return {
            "status": status,
            "aris": _fmt_periods(aris.red),
            "fastf1": _fmt_periods(ff1.red),
            "detail": ",".join(detail) or "—",
        }
    if name == "wet":
        a, b = set(aris.wet_laps), set(ff1.wet_laps)
        ever_ok = aris.wet_ever == ff1.wet_ever
        laps_ok = a == b
        status = "pass" if ever_ok and laps_ok else "mismatch"
        return {
            "status": status,
            "aris": f"ever={aris.wet_ever} laps={aris.wet_laps or '—'}",
            "fastf1": f"ever={ff1.wet_ever} laps={ff1.wet_laps or '—'}",
            "ever_ok": ever_ok,
            "laps_ok": laps_ok,
            "aris_only_n": len(a - b),
            "ff1_only_n": len(b - a),
        }
    raise ValueError(name)


def compare_facts(aris: RaceFacts, ff1: RaceFacts) -> dict[str, Any]:
    fields = {name: compare_field(name, aris, ff1) for name in FIELDS}
    mismatch_n = sum(1 for row in fields.values() if row["status"] != "pass")
    return {
        "year": aris.year or ff1.year,
        "round": aris.round or ff1.round,
        "circuit": aris.circuit or ff1.circuit,
        "fields": fields,
        "mismatch_n": mismatch_n,
        "ok": mismatch_n == 0,
        "aris_notes": aris.notes,
        "ff1_notes": ff1.notes,
        "aris_race_control_n": aris.race_control_n,
        "ff1_race_control_n": ff1.race_control_n,
    }


def iter_race_fields(replay_root: Path) -> list[Path]:
    if not replay_root.is_dir():
        return []
    return sorted(replay_root.glob("*/*/race_field.json"))


def load_field(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_fastf1_session(year: int, round_number: int):
    from backend.cache import enable_fastf1_cache
    from backend.sessions import load_session

    enable_fastf1_cache()
    return load_session(
        int(year), int(round_number), "R", telemetry=False, weather=True, messages=True
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {name: Counter(r["fields"][name]["status"] for r in rows) for name in FIELDS}
    patterns: list[str] = []
    empty_rc = sum(1 for r in rows if int(r.get("aris_race_control_n") or 0) == 0)
    ff1_rc = sum(1 for r in rows if int(r.get("ff1_race_control_n") or 0) > 0)
    if empty_rc == len(rows) and rows:
        patterns.append(
            f"race_control.json is empty for all {empty_rc} races "
            f"({ff1_rc} of those have FastF1 race_control_messages). "
            "Restart type therefore cannot be derived from ARIS packs."
        )
    red_restart = [
        r
        for r in rows
        if r["fields"]["red"]["status"] == "mismatch"
        and r["fields"]["red"].get("detail") == "restart_type"
    ]
    if red_restart:
        patterns.append(
            "Red-flag lap ranges match on "
            f"{len(red_restart)} race(s) but restart type is missing in ARIS."
        )
    wet_ever_ok_laps_bad = [
        r
        for r in rows
        if r["fields"]["wet"]["status"] == "mismatch"
        and r["fields"]["wet"].get("ever_ok")
        and not r["fields"]["wet"].get("laps_ok")
    ]
    if wet_ever_ok_laps_bad:
        patterns.append(
            "Wet 'ever' flag matches on "
            f"{len(wet_ever_ok_laps_bad)} race(s) but per-lap rainfall sets differ "
            "(ARIS interpolates weather rows by index; FastF1 uses nearest-in-time)."
        )
    wet_ever_bad = [
        r
        for r in rows
        if r["fields"]["wet"]["status"] == "mismatch" and not r["fields"]["wet"].get("ever_ok")
    ]
    if wet_ever_bad:
        patterns.append(f"Wet ever-flag disagrees on {len(wet_ever_bad)} race(s).")
    dnf_mm = [r for r in rows if r["fields"]["dnf"]["status"] != "pass"]
    if dnf_mm:
        patterns.append(f"DNF set disagrees on {len(dnf_mm)} race(s).")
    dns_mm = [r for r in rows if r["fields"]["dns"]["status"] != "pass"]
    if dns_mm:
        patterns.append(f"DNS set disagrees on {len(dns_mm)} race(s).")
    sc_mm = [r for r in rows if r["fields"]["sc"]["status"] != "pass"]
    vsc_mm = [r for r in rows if r["fields"]["vsc"]["status"] != "pass"]
    red_period_mm = [
        r
        for r in rows
        if r["fields"]["red"]["status"] != "pass"
        and "periods" in str(r["fields"]["red"].get("detail") or "")
    ]
    if sc_mm:
        patterns.append(f"SC periods disagree on {len(sc_mm)} race(s) (from TrackStatus).")
    if vsc_mm:
        patterns.append(f"VSC periods disagree on {len(vsc_mm)} race(s) (from TrackStatus).")
    if red_period_mm:
        patterns.append(
            f"Red-flag periods disagree on {len(red_period_mm)} race(s) "
            "(from TrackStatus)."
        )
    return {
        "races": len(rows),
        "all_pass": sum(1 for r in rows if r["ok"]),
        "any_mismatch": sum(1 for r in rows if not r["ok"]),
        "by_field": {name: dict(counts[name]) for name in FIELDS},
        "patterns": patterns,
        "empty_aris_race_control": empty_rc,
        "ff1_has_race_control": ff1_rc,
    }


def format_table(rows: list[dict[str, Any]]) -> str:
    header = (
        f"{'YEAR':>4}  {'RND':>3}  {'CIRCUIT':<18}  "
        f"{'DNF':<8}  {'DNS':<8}  {'SC':<8}  {'VSC':<8}  {'RED':<8}  {'WET':<8}  MM"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        fields = row["fields"]
        cells = {
            name: ("PASS" if fields[name]["status"] == "pass" else "MISMATCH")
            for name in FIELDS
        }
        circuit = (row.get("circuit") or "")[:18]
        lines.append(
            f"{row.get('year')!s:>4}  {row.get('round')!s:>3}  {circuit:<18}  "
            f"{cells['dnf']:<8}  {cells['dns']:<8}  {cells['sc']:<8}  "
            f"{cells['vsc']:<8}  {cells['red']:<8}  {cells['wet']:<8}  "
            f"{row.get('mismatch_n')}"
        )
    return "\n".join(lines)


def format_mismatches(rows: list[dict[str, Any]]) -> str:
    bad = [r for r in rows if not r["ok"]]
    if not bad:
        return "No per-field mismatches."
    chunks: list[str] = []
    for row in bad:
        chunks.append(f"{row.get('year')} R{row.get('round')} {row.get('circuit')}:")
        for name in FIELDS:
            cell = row["fields"][name]
            if cell["status"] == "pass":
                continue
            chunks.append(
                f"  {name}: ARIS={cell.get('aris')}  FastF1={cell.get('fastf1')}"
                + (f"  ({cell['detail']})" if cell.get("detail") and cell["detail"] != "—" else "")
            )
    return "\n".join(chunks)


def _facts_json(facts: RaceFacts) -> dict[str, Any]:
    payload = asdict(facts)
    for key in ("sc", "vsc", "red"):
        payload[key] = [asdict(p) if not isinstance(p, dict) else p for p in getattr(facts, key)]
    payload["dnf"] = [list(x) for x in facts.dnf]
    return payload


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Audit R2 race_field.json vs FastF1")
    parser.add_argument("--replay-root", default=str(DEFAULT_REPLAY))
    parser.add_argument("--year", type=int)
    parser.add_argument("--round", type=int, dest="round_number")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)

    replay_root = Path(args.replay_root)
    paths = iter_race_fields(replay_root)
    if args.year:
        paths = [p for p in paths if p.parent.parent.name == str(args.year)]
    if args.round_number:
        paths = [p for p in paths if p.parent.name == str(args.round_number)]
    if not paths:
        print(f"no race_field.json under {replay_root}")
        return 1

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in paths:
        try:
            year = int(path.parent.parent.name)
            rnd = int(path.parent.name)
        except ValueError:
            continue
        _log.info("auditing %s R%s", year, rnd)
        try:
            field = load_field(path)
            aris = facts_from_field(field)
            if not aris.year:
                aris.year = year
            if not aris.round:
                aris.round = rnd
            sess = load_fastf1_session(year, rnd)
            ff1 = facts_from_session(sess, year, rnd, aris.circuit)
            report = compare_facts(aris, ff1)
            report["path"] = str(path)
            report["aris_facts"] = _facts_json(aris)
            report["ff1_facts"] = _facts_json(ff1)
            rows.append(report)
        except Exception as extra:
            _log.exception("FAILED %s R%s: %s", year, rnd, extra)
            failures.append(f"{year} R{rnd}: {extra}")
            rows.append(
                {
                    "year": year,
                    "round": rnd,
                    "circuit": "",
                    "fields": {
                        name: {"status": "fail", "aris": "—", "fastf1": str(extra)}
                        for name in FIELDS
                    },
                    "mismatch_n": len(FIELDS),
                    "ok": False,
                    "aris_notes": [f"load_error:{extra}"],
                    "ff1_notes": [],
                    "aris_race_control_n": 0,
                    "ff1_race_control_n": 0,
                }
            )

    summary = summarize(rows)
    print(format_table(rows))
    print()
    print(
        f"{summary['races']} races  {summary['all_pass']} all-pass  "
        f"{summary['any_mismatch']} with mismatches"
    )
    print("By field:", json.dumps(summary["by_field"], sort_keys=True))
    if summary["patterns"]:
        print("PATTERNS:")
        for line in summary["patterns"]:
            print(f"  - {line}")
    print()
    print(format_mismatches(rows))
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"summary": summary, "races": rows}, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"wrote {out}")
    if failures:
        print(f"{len(failures)} race(s) failed to load")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
