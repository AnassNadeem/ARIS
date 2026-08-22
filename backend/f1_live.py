"""F1 livetiming SignalR ingest — works during a live session without OpenF1 auth.

OpenF1's public REST API returns 401 while a session is in progress. The F1
SignalR Core hub (`livetiming.formula1.com/signalrcore`) still serves the
timing snapshot + deltas used by FastF1's recorder. We keep the latest
TimingData / Position.z / WeatherData in memory for `/api/live/*`.
"""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

_log = logging.getLogger("aris.f1_live")

SESSION_INFO_URL = "https://livetiming.formula1.com/static/SessionInfo.json"
NEGOTIATE_URL = "https://livetiming.formula1.com/signalrcore/negotiate"
WS_URL = "wss://livetiming.formula1.com/signalrcore"

TOPICS = [
    "Heartbeat",
    "DriverList",
    "TimingData",
    "TimingAppData",
    "TimingStats",
    "WeatherData",
    "TrackStatus",
    "SessionStatus",
    "ExtrapolatedClock",
    "RaceControlMessages",
    "Position.z",
    "CarData.z",
    "LapCount",
    "TopThree",
    "SessionInfo",
    "SessionData",
]

_LOCK = threading.RLock()
_TOPICS: dict[str, Any] = {}
_POSITIONS: dict[str, dict[str, Any]] = {}
_CAR_DATA: dict[str, dict[str, Any]] = {}
_STARTED = False
_THREAD: threading.Thread | None = None
_LAST_MSG = 0.0
_CONNECTED = False
_ERROR: str | None = None

_Z_TOPICS = {"Position.z", "CarData.z"}

# Official F1 livetiming CarData channel ids.
CHAN_RPM = "0"
CHAN_SPEED = "2"
CHAN_GEAR = "3"
CHAN_THROTTLE = "4"
CHAN_BRAKE = "5"
CHAN_DRS = "45"


def parse_laptime_ms(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("Value")
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not text or text in {"-", "None"}:
        return None
    try:
        if ":" in text:
            parts = text.split(":")
            if len(parts) == 2:
                return int(round(float(parts[0]) * 60_000 + float(parts[1]) * 1000))
            if len(parts) == 3:
                return int(
                    round(
                        float(parts[0]) * 3_600_000
                        + float(parts[1]) * 60_000
                        + float(parts[2]) * 1000
                    )
                )
        return int(round(float(text) * 1000))
    except (TypeError, ValueError):
        return None


def parse_gap_s(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("Value")
    if value is None or value == "":
        return None
    text = str(value).strip().lstrip("+")
    if not text:
        return None
    upper = text.upper()
    if upper in {"LAP", "LEADER"} or "LAP" in upper:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_remaining_s(value: Any) -> int | None:
    if not value:
        return None
    parts = str(value).strip().split(":")
    try:
        nums = [int(float(p)) for p in parts]
    except (TypeError, ValueError):
        return None
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 1:
        return nums[0]
    return None


def sector_colour(sec: Any) -> str:
    if not isinstance(sec, dict) or not sec.get("Value"):
        return "grey"
    if sec.get("OverallFastest"):
        return "purple"
    if sec.get("PersonalFastest"):
        return "green"
    return "yellow"


def deep_merge(dst: Any, src: Any) -> Any:
    if isinstance(dst, dict) and isinstance(src, dict):
        out = dict(dst)
        for key, val in src.items():
            out[key] = deep_merge(out[key], val) if key in out else val
        return out
    if isinstance(dst, list) and isinstance(src, list):
        out = list(dst)
        for i, val in enumerate(src):
            if i < len(out):
                out[i] = deep_merge(out[i], val)
            else:
                out.append(val)
        return out
    return src


def _decode_z(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, (dict, list)):
        return payload
    text = str(payload).strip().strip('"')
    if not text:
        return None
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    try:
        raw = zlib.decompress(base64.b64decode(text), -zlib.MAX_WBITS)
        return json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return None


def _local_dt(raw: str | None, gmt_offset: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        hours, minutes, seconds = 0, 0, 0
        if gmt_offset:
            sign = -1 if str(gmt_offset).startswith("-") else 1
            bits = str(gmt_offset).lstrip("+-").split(":")
            try:
                hours = int(bits[0]) if bits else 0
                minutes = int(bits[1]) if len(bits) > 1 else 0
                seconds = int(bits[2]) if len(bits) > 2 else 0
            except ValueError:
                hours, minutes, seconds = 0, 0, 0
        dt = dt.replace(tzinfo=timezone(timedelta(hours=sign * hours, minutes=sign * minutes, seconds=sign * seconds)))
    return dt.astimezone(timezone.utc)


def fetch_session_info() -> dict[str, Any] | None:
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True, headers={"User-Agent": "ARIS/1.0"}) as client:
            r = client.get(SESSION_INFO_URL)
            r.raise_for_status()
            text = r.content.decode("utf-8-sig")
            data = json.loads(text)
            return data if isinstance(data, dict) else None
    except Exception as extra:
        _log.debug("SessionInfo fetch failed: %s", extra)
        return None


def session_info_is_live(info: dict[str, Any] | None, now: datetime | None = None) -> bool:
    if not info:
        return False
    now = now or datetime.now(timezone.utc)
    archive = str((info.get("ArchiveStatus") or {}).get("Status") or "")
    status = str(info.get("SessionStatus") or "")
    if archive.lower() == "complete" or status.lower() in {"finished", "ends", "finalised", "finalized"}:
        start = _local_dt(info.get("StartDate"), info.get("GmtOffset"))
        end = _local_dt(info.get("EndDate"), info.get("GmtOffset"))
        if end is not None and now > end + timedelta(minutes=10):
            return False
        if archive.lower() == "complete":
            return False
    if archive.lower() == "generating":
        return True
    if status.lower() in {"started", "inactive", "aborted"}:
        start = _local_dt(info.get("StartDate"), info.get("GmtOffset"))
        end = _local_dt(info.get("EndDate"), info.get("GmtOffset"))
        if start is None:
            return status.lower() == "started"
        if now < start - timedelta(minutes=10):
            return False
        if end is not None and now > end + timedelta(minutes=20):
            return False
        return True
    start = _local_dt(info.get("StartDate"), info.get("GmtOffset"))
    end = _local_dt(info.get("EndDate"), info.get("GmtOffset"))
    if start is None:
        return False
    if end is None:
        end = start + timedelta(hours=2)
    return start - timedelta(minutes=5) <= now <= end + timedelta(minutes=15)


def _store_topic(topic: str, payload: Any) -> None:
    global _LAST_MSG
    if topic in _Z_TOPICS:
        decoded = _decode_z(payload)
        if topic == "Position.z":
            _ingest_positions(decoded)
        elif topic == "CarData.z":
            _ingest_cardata(decoded)
        with _LOCK:
            if decoded is not None:
                _TOPICS[topic] = decoded
            _LAST_MSG = time.time()
        return
    with _LOCK:
        if topic in _TOPICS and isinstance(_TOPICS[topic], (dict, list)) and isinstance(payload, (dict, list)):
            _TOPICS[topic] = deep_merge(_TOPICS[topic], payload)
        else:
            _TOPICS[topic] = payload
        _LAST_MSG = time.time()


def _ingest_positions(decoded: Any) -> None:
    if not isinstance(decoded, dict):
        return
    samples = decoded.get("Position") or decoded.get("Entries")
    latest_entries: dict[str, Any] | None = None
    if isinstance(samples, list) and samples:
        last = samples[-1]
        if isinstance(last, dict):
            latest_entries = last.get("Entries") if "Entries" in last else last
    elif isinstance(decoded.get("Entries"), dict):
        latest_entries = decoded["Entries"]
    if not isinstance(latest_entries, dict):
        return
    with _LOCK:
        for num, row in latest_entries.items():
            if not isinstance(row, dict):
                continue
            prev = _POSITIONS.get(str(num), {})
            merged = dict(prev)
            merged.update(row)
            _POSITIONS[str(num)] = merged


def _ingest_cardata(decoded: Any) -> None:
    if not isinstance(decoded, dict):
        return
    samples = decoded.get("Entries")
    latest_cars: dict[str, Any] | None = None
    if isinstance(samples, list) and samples:
        last = samples[-1]
        if isinstance(last, dict):
            latest_cars = last.get("Cars") if "Cars" in last else last
    elif isinstance(decoded.get("Cars"), dict):
        latest_cars = decoded["Cars"]
    if not isinstance(latest_cars, dict):
        return
    with _LOCK:
        for num, row in latest_cars.items():
            if not isinstance(row, dict):
                continue
            channels = row.get("Channels") if isinstance(row.get("Channels"), dict) else row
            if not isinstance(channels, dict):
                continue
            prev = _CAR_DATA.get(str(num), {})
            merged = dict(prev)
            merged.update(
                {
                    "rpm": channels.get(CHAN_RPM, channels.get(0, prev.get("rpm"))),
                    "speed": channels.get(CHAN_SPEED, channels.get(2, prev.get("speed"))),
                    "gear": channels.get(CHAN_GEAR, channels.get(3, prev.get("gear"))),
                    "throttle": channels.get(CHAN_THROTTLE, channels.get(4, prev.get("throttle"))),
                    "brake": channels.get(CHAN_BRAKE, channels.get(5, prev.get("brake"))),
                    "drs": channels.get(CHAN_DRS, channels.get(45, prev.get("drs"))),
                }
            )
            _CAR_DATA[str(num)] = merged


def _apply_snapshot(result: Any) -> None:
    if not isinstance(result, dict):
        return
    for topic, payload in result.items():
        _store_topic(str(topic), payload)


def _on_feed(msg: Any) -> None:
    if isinstance(msg, list) and msg:
        topic = str(msg[0])
        payload = msg[1] if len(msg) > 1 else None
        _store_topic(topic, payload)


def _run_loop() -> None:
    global _CONNECTED, _ERROR
    try:
        from signalrcore.hub_connection_builder import HubConnectionBuilder
        from signalrcore.messages.completion_message import CompletionMessage
    except Exception as extra:
        _ERROR = f"signalrcore unavailable: {extra}"
        _log.warning(_ERROR)
        return

    backoff = 1.0
    while True:
        conn = None
        try:
            import requests

            pre = requests.options(NEGOTIATE_URL, timeout=10)
            cookie = pre.cookies.get("AWSALBCORS")
            headers = {"Cookie": f"AWSALBCORS={cookie}"} if cookie else {}
            opened = threading.Event()

            def on_open() -> None:
                opened.set()

            def on_close() -> None:
                global _CONNECTED
                _CONNECTED = False

            def on_error(err: Any) -> None:
                global _ERROR
                _ERROR = str(err)

            def on_invoke(msg: Any) -> None:
                result = getattr(msg, "result", None)
                if result is None and isinstance(msg, dict):
                    result = msg.get("result")
                if isinstance(msg, CompletionMessage):
                    result = msg.result
                _apply_snapshot(result)

            conn = HubConnectionBuilder().with_url(WS_URL, options={"verify_ssl": True, "headers": headers}).configure_logging(40).build()
            conn.on_open(on_open)
            conn.on_close(on_close)
            conn.on_error(on_error)
            conn.on("feed", _on_feed)
            conn.start()
            if not opened.wait(timeout=12):
                raise TimeoutError("SignalR open timeout")
            conn.send("Subscribe", [TOPICS], on_invocation=on_invoke)
            _CONNECTED = True
            _ERROR = None
            backoff = 1.0
            _log.info("F1 livetiming SignalR connected")
            stale = 0
            while True:
                time.sleep(2)
                if not opened.is_set():
                    break
                if _LAST_MSG and time.time() - _LAST_MSG > 45:
                    stale += 1
                    if stale >= 2:
                        raise TimeoutError("SignalR heartbeat stale")
                else:
                    stale = 0
        except Exception as extra:
            _CONNECTED = False
            _ERROR = str(extra)
            _log.warning("F1 livetiming reconnect in %.0fs: %s", backoff, extra)
            try:
                if conn is not None:
                    conn.stop()
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(30.0, backoff * 1.7)


def start_background() -> None:
    global _STARTED, _THREAD
    if _STARTED:
        return
    _STARTED = True
    _THREAD = threading.Thread(target=_run_loop, name="aris-f1-live", daemon=True)
    _THREAD.start()
    _log.info("F1 livetiming ingest thread started")


def snapshot() -> dict[str, Any]:
    with _LOCK:
        return {
            "topics": {k: v for k, v in _TOPICS.items()},
            "positions": dict(_POSITIONS),
            "cardata": dict(_CAR_DATA),
            "connected": _CONNECTED,
            "last_msg": _LAST_MSG,
            "error": _ERROR,
            "age_s": (time.time() - _LAST_MSG) if _LAST_MSG else None,
        }


def topic(name: str) -> Any:
    with _LOCK:
        return _TOPICS.get(name)


def positions() -> dict[str, dict[str, Any]]:
    with _LOCK:
        return dict(_POSITIONS)


def cardata() -> dict[str, dict[str, Any]]:
    with _LOCK:
        return dict(_CAR_DATA)


def connected() -> bool:
    return _CONNECTED and bool(_LAST_MSG) and (time.time() - _LAST_MSG) < 60
