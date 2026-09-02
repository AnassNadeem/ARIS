#!/usr/bin/env python
"""Upload prebuilt replay JSON to Cloudflare R2 (S3-compatible).

Env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME

    python deploy/r2_upload.py --path replay/2025/15/
    python deploy/r2_upload.py --path replay/ --reupload-all
    python deploy/r2_upload.py --file data/replay_r2/replay/2025/15/race_field.json \\
        --key replay/2025/15/race_field.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCAL = ROOT / "data" / "replay_r2"
PUBLIC_BASE = (os.environ.get("NEXT_PUBLIC_R2_BASE_URL") or "https://pub-9429cde26be84c4c8034f0b5873b9a7d.r2.dev").rstrip("/")
# Replay JSON is rebuilt in place at a stable URL. Immutable long-cache would
# hide every subsequent upload from browsers and Cloudflare's edge.
CACHE_CONTROL = "public, max-age=3600, must-revalidate"
CORS_ORIGINS = [
    "https://arisf1.tech",
    "https://www.arisf1.tech",
    "https://aris-frontend-590.pages.dev",
    "https://*.aris-frontend-590.pages.dev",
    "http://localhost:3000",
]

_log = logging.getLogger("aris.r2")
_BOTO_OK: bool | None = None


def _env(name: str) -> str:
    val = (os.environ.get(name) or "").strip()
    if not val:
        raise SystemExit(f"missing env var {name}")
    return val


def r2_client():
    try:
        import boto3
        from botocore.config import Config
    except ImportError as extra:
        raise SystemExit("boto3 is required: pip install boto3") from extra

    account = _env("R2_ACCOUNT_ID")
    endpoint = f"https://{account}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 1, "mode": "standard"},
            connect_timeout=5,
            read_timeout=10,
        ),
        region_name="auto",
    )


def _boto_usable(client, bucket: str) -> bool:
    global _BOTO_OK
    if _BOTO_OK is not None:
        return _BOTO_OK
    key = (os.environ.get("R2_ACCESS_KEY_ID") or "").strip().lower()
    if key in {"", "wrangler-oauth", "dummy", "missing"}:
        _BOTO_OK = False
        return False
    try:
        client.head_bucket(Bucket=bucket)
        _BOTO_OK = True
    except Exception:
        _BOTO_OK = False
    return _BOTO_OK


def _wrangler(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    exe = "npx.cmd" if os.name == "nt" else "npx"
    return subprocess.run(
        [exe, "--yes", "wrangler", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _ensure_cors_wrangler(bucket: str) -> None:
    payload = {
        "rules": [
            {
                "allowed": {
                    "origins": list(CORS_ORIGINS),
                    "methods": ["GET", "HEAD"],
                    "headers": ["*"],
                },
                "exposedHeaders": ["ETag", "Content-Length"],
                "maxAgeSeconds": 31536000,
            }
        ]
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle)
        cors_path = handle.name
    try:
        result = _wrangler(["r2", "bucket", "cors", "set", bucket, "--file", cors_path, "--force"])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "wrangler cors set failed").strip())
        _log.info("CORS set on bucket %s for %s", bucket, ", ".join(CORS_ORIGINS))
    finally:
        Path(cors_path).unlink(missing_ok=True)


def ensure_cors(client, bucket: str) -> None:
    cors_rules = {
        "CORSRules": [
            {
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "HEAD"],
                "AllowedOrigins": list(CORS_ORIGINS),
                "ExposeHeaders": ["ETag", "Content-Length"],
                "MaxAgeSeconds": 31536000,
            }
        ]
    }
    try:
        if _boto_usable(client, bucket):
            client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors_rules)
            _log.info("CORS set on bucket %s for %s", bucket, ", ".join(CORS_ORIGINS))
            return
    except Exception as extra:
        _log.warning("boto3 CORS failed (%s); trying wrangler", extra)
    try:
        _ensure_cors_wrangler(bucket)
    except Exception as extra:
        _log.warning("could not set bucket CORS: %s", extra)


def object_exists(client, bucket: str, key: str) -> bool:
    try:
        if _boto_usable(client, bucket):
            client.head_object(Bucket=bucket, Key=key)
            return True
    except Exception:
        pass
    url = f"{PUBLIC_BASE}/{key}"
    try:
        req = urllib.request.Request(
            url,
            method="HEAD",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=20) as res:
            return 200 <= int(res.status) < 300
    except Exception:
        return False


def _upload_wrangler(bucket: str, local: Path, key: str) -> None:
    result = _wrangler(
        [
            "r2",
            "object",
            "put",
            f"{bucket}/{key}",
            "--file",
            str(local),
            "--content-type",
            "application/json",
            "--cache-control",
            CACHE_CONTROL,
            "--remote",
            "--force",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "wrangler put failed").strip())


def upload_file(client, bucket: str, local: Path, key: str) -> None:
    extra = {
        "ContentType": "application/json",
        "CacheControl": CACHE_CONTROL,
    }
    uploaded = False
    try:
        if _boto_usable(client, bucket):
            client.upload_file(str(local), bucket, key, ExtraArgs=extra)
            uploaded = True
    except Exception as extra_err:
        _log.warning("boto3 upload failed (%s); trying wrangler", extra_err)
    if not uploaded:
        _upload_wrangler(bucket, local, key)
    _log.info("uploaded s3://%s/%s (%s bytes)", bucket, key, local.stat().st_size)


def upload_prefix(client, bucket: str, prefix: str, local_root: Path) -> int:
    """Upload every .json under local_root / prefix. Returns count."""
    prefix = prefix.strip("/").replace("\\", "/")
    folder = local_root / prefix
    if not folder.exists():
        _log.warning("local path missing: %s", folder)
        return 0
    count = 0
    for path in folder.rglob("*.json"):
        rel = path.relative_to(local_root).as_posix()
        upload_file(client, bucket, path, rel)
        count += 1
    return count


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Upload replay JSON to Cloudflare R2")
    parser.add_argument(
        "--path",
        default="",
        help="prefix under data/replay_r2, e.g. replay/2025/15/",
    )
    parser.add_argument("--file", default="", help="single local JSON file")
    parser.add_argument("--key", default="", help="R2 object key (with --file)")
    parser.add_argument("--local-root", default=str(DEFAULT_LOCAL))
    parser.add_argument("--skip-cors", action="store_true")
    parser.add_argument(
        "--reupload-all",
        action="store_true",
        help=(
            "Walk local replay JSON and upload every file found. Does not skip "
            "objects already on R2. Use after a cache-header change or in-place rebuild."
        ),
    )
    args = parser.parse_args(argv)
    _load_env()

    client = r2_client()
    bucket = _env("R2_BUCKET_NAME")
    if not args.skip_cors:
        ensure_cors(client, bucket)

    if args.reupload_all:
        prefix = args.path or "replay/"
        n = upload_prefix(client, bucket, prefix, Path(args.local_root))
        _log.info("re-uploaded %s objects under %s", n, prefix)
        return 0 if n else 1

    if args.file:
        local = Path(args.file)
        if not local.is_file():
            _log.error("file not found: %s", local)
            return 1
        key = args.key or local.name
        upload_file(client, bucket, local, key)
        return 0

    prefix = args.path or "replay/"
    n = upload_prefix(client, bucket, prefix, Path(args.local_root))
    _log.info("uploaded %s objects under %s", n, prefix)
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
