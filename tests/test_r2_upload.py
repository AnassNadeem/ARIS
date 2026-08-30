"""R2 upload cache headers and bulk re-upload of local replay JSON."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy import r2_upload  # noqa: E402


def test_cache_control_is_short_revalidate():
    assert "immutable" not in r2_upload.CACHE_CONTROL
    assert "max-age=3600" in r2_upload.CACHE_CONTROL
    assert "must-revalidate" in r2_upload.CACHE_CONTROL


def test_upload_file_sends_short_cache(monkeypatch, tmp_path):
    local = tmp_path / "race_field.json"
    local.write_text("{}", encoding="utf-8")
    seen: dict[str, object] = {}

    class Client:
        def upload_file(self, *_a, **kwargs):
            seen["extra"] = kwargs.get("ExtraArgs")

    monkeypatch.setattr(r2_upload, "_boto_usable", lambda *_a, **_k: True)
    r2_upload.upload_file(Client(), "bucket", local, "replay/2024/1/race_field.json")
    extra = seen["extra"]
    assert isinstance(extra, dict)
    assert extra["CacheControl"] == r2_upload.CACHE_CONTROL
    assert extra["CacheControl"] != "public, max-age=31536000, immutable"


def test_reupload_all_walks_local_json(monkeypatch, tmp_path):
    replay = tmp_path / "replay" / "2024" / "1"
    replay.mkdir(parents=True)
    field = replay / "race_field.json"
    ghost = replay / "ghost_VER.json"
    field.write_text("{}", encoding="utf-8")
    ghost.write_text("{}", encoding="utf-8")
    (tmp_path / "replay" / "skip.txt").write_text("no", encoding="utf-8")
    uploaded: list[str] = []

    monkeypatch.setattr(r2_upload, "_load_env", lambda: None)
    monkeypatch.setattr(r2_upload, "r2_client", lambda: SimpleNamespace())
    monkeypatch.setattr(r2_upload, "_env", lambda name: "aris-replay")
    monkeypatch.setattr(r2_upload, "ensure_cors", lambda *_a, **_k: None)
    monkeypatch.setattr(
        r2_upload,
        "upload_file",
        lambda _c, _b, local, key: uploaded.append(key),
    )

    code = r2_upload.main(
        ["--path", "replay/", "--reupload-all", "--local-root", str(tmp_path), "--skip-cors"]
    )
    assert code == 0
    assert sorted(uploaded) == [
        "replay/2024/1/ghost_VER.json",
        "replay/2024/1/race_field.json",
    ]
