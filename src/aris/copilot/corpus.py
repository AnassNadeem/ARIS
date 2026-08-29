"""Load Copilot retrieval corpora: FIA regs, driver/track priors, ARIS docs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
REGS_DIR = _REPO / "data" / "regs"
PRIORS_DIR = _REPO / "data" / "priors"
DOCS_DIR = _REPO / "docs"

_DOC_GLOBS = (
    "PHASE-T9*.md",
    "PHASE-T10*.md",
    "model-status.md",
    "how-recommend-works.md",
)

MAX_CHARS = 1800
MIN_CHARS = 80


def load_prior_files() -> dict[str, Any]:
    drivers_path = PRIORS_DIR / "drivers.json"
    circuits_path = PRIORS_DIR / "circuits.json"
    drivers = json.loads(drivers_path.read_text(encoding="utf-8")) if drivers_path.exists() else {}
    circuits = json.loads(circuits_path.read_text(encoding="utf-8")) if circuits_path.exists() else {}
    return {"drivers": drivers, "circuits": circuits}


def _split_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        meta[key.strip()] = val.strip()
    return meta, parts[2]


def _slug(text: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return token[:60] or "section"


def _chunk_markdown(body: str) -> list[tuple[str, str]]:
    text = body.strip()
    if not text:
        return []
    parts = re.split(r"(?m)^## ", text)
    out: list[tuple[str, str]] = []
    for i, part in enumerate(parts):
        block = part.strip()
        if not block:
            continue
        if i == 0:
            heading = ""
            for line in block.splitlines():
                if line.startswith("# "):
                    heading = line[2:].strip()
                    break
            section = heading or "overview"
            payload = block
        else:
            heading = block.split("\n", 1)[0].strip()
            section = heading
            payload = "## " + block
        if len(payload) < MIN_CHARS:
            continue
        if len(payload) <= MAX_CHARS:
            out.append((section, payload))
            continue
        paras = re.split(r"\n\s*\n", payload)
        buf = ""
        for para in paras:
            if len(buf) + len(para) + 2 <= MAX_CHARS:
                buf = f"{buf}\n\n{para}".strip()
                continue
            if buf:
                out.append((section, buf))
            buf = para
        if buf:
            out.append((section, buf))
    return out or [("overview", text[:MAX_CHARS])]


def _year_from_meta(meta: dict[str, str], fallback: int | None = None) -> int | None:
    raw = meta.get("year")
    if raw and raw.isdigit():
        return int(raw)
    return fallback


def load_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    chunks.extend(_load_regs())
    chunks.extend(_load_priors())
    chunks.extend(_load_aris_docs())
    return chunks


def _load_regs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not REGS_DIR.is_dir():
        return out
    for path in sorted(REGS_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = _split_front_matter(raw)
        doc_id = str(meta.get("id") or path.stem)
        title = str(meta.get("title") or path.stem.replace("-", " "))
        year = _year_from_meta(meta, 2025)
        for section, text in _chunk_markdown(body):
            slug = _slug(section) if section and section.lower() not in {title.lower(), "overview"} else ""
            chunk_id = f"fia_reg:{doc_id}" + (f":{slug}" if slug else "")
            out.append(
                {
                    "chunk_id": chunk_id,
                    "text": text.strip(),
                    "source": "fia_reg",
                    "title": title,
                    "section": section or title,
                    "year": year,
                    "path": str(path.relative_to(_REPO)).replace("\\", "/"),
                }
            )
    return out


def _load_priors() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    files = load_prior_files()
    for code, rec in (files.get("drivers") or {}).items():
        text = str(rec.get("text") or "")
        if not text:
            continue
        name = rec.get("name") or code
        payload = (
            f"{name} ({code}). Tyre style: {rec.get('tyre_style')}. {text} "
            f"Typical stint lengths: {json.dumps(rec.get('typical_stint_laps') or {})}. "
            f"Lap-time variance {rec.get('lap_time_variance_s')} s. "
            f"Overtakes per race {rec.get('overtakes_per_race')}."
        )
        out.append(
            {
                "chunk_id": f"driver_prior:{code}",
                "text": payload,
                "source": "driver_prior",
                "title": f"{name} tyre and pace prior",
                "section": str(code),
                "year": rec.get("year"),
                "path": "data/priors/drivers.json",
            }
        )
    for cid, rec in (files.get("circuits") or {}).items():
        text = str(rec.get("text") or "")
        if not text:
            continue
        name = rec.get("name") or cid
        payload = (
            f"{name} (id={cid}). Degradation: {rec.get('deg')}. {text} "
            f"Historical SC rate {rec.get('typical_sc_rate')}. "
            f"Lap length {rec.get('lap_length_m')} m. "
            f"Aliases: {', '.join(rec.get('aliases') or [])}."
        )
        out.append(
            {
                "chunk_id": f"circuit_prior:{cid}",
                "text": payload,
                "source": "circuit_prior",
                "title": f"{name} circuit prior",
                "section": str(cid),
                "year": rec.get("year"),
                "path": "data/priors/circuits.json",
            }
        )
    return out


def _load_aris_docs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for pattern in _DOC_GLOBS:
        for path in sorted(DOCS_DIR.glob(pattern)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            body = path.read_text(encoding="utf-8")
            stem = path.stem
            for section, text in _chunk_markdown(body):
                slug = _slug(section)
                chunk_id = f"aris_doc:{stem}" + (f":{slug}" if slug and slug != "overview" else "")
                out.append(
                    {
                        "chunk_id": chunk_id,
                        "text": text.strip(),
                        "source": "aris_doc",
                        "title": stem.replace("-", " "),
                        "section": section or stem,
                        "year": 2026,
                        "path": str(path.relative_to(_REPO)).replace("\\", "/"),
                    }
                )
    return out
