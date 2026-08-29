#!/usr/bin/env python
"""Upload prebuilt replay JSON to Cloudflare R2 (S3-compatible).

Env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME

    python deploy/r2_upload.py --path replay/2025/15/
    python deploy/r2_upload.py --file data/replay_r2/replay/2025/15/race_field.json \\
        --key replay/2025/15/race_field.json
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCAL = ROOT / "data" / "replay_r2"
CORS_ORIGIN = "https://aris-frontend-590.pages.dev"

_log = logging.getLogger("aris.r2")


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
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def ensure_cors(client, bucket: str) -> None:
    try:
        client.put_bucket_cors(
            Bucket=bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["GET", "HEAD"],
                        "AllowedOrigins": [
                            CORS_ORIGIN,
                            "http://localhost:3000",
                            "http://127.0.0.1:3000",
                        ],
                        "ExposeHeaders": ["ETag", "Content-Length"],
                        "MaxAgeSeconds": 31536000,
                    }
                ]
            },
        )
        _log.info("CORS set on bucket %s for %s", bucket, CORS_ORIGIN)
    except Exception as extra:
        _log.warning("could not set bucket CORS: %s", extra)


def object_exists(client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def upload_file(client, bucket: str, local: Path, key: str) -> None:
    extra = {
        "ContentType": "application/json",
        "CacheControl": "public, max-age=31536000, immutable",
    }
    client.upload_file(str(local), bucket, key, ExtraArgs=extra)
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
    args = parser.parse_args(argv)

    client = r2_client()
    bucket = _env("R2_BUCKET_NAME")
    if not args.skip_cors:
        ensure_cors(client, bucket)

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
