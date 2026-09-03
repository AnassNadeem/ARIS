# Contributing

## Setup

Follow the **Getting started** section in [`README.md`](./README.md) (`uv sync --extra
dev` or the pip fallback). Do not duplicate that flow here.

## Before opening a PR

1. `uv run ruff check` (or `ruff check`) — CI also fails on new Ruff findings vs
   `ruff-baseline.json`.
2. `uv run pytest` — same deselections as CI are optional locally; the full suite
   should not introduce new failures.

DB-integration tests require `ARIS_DB_URL` set locally. Without it they are
skipped or fail with a connection error; that is expected, not a bug. CI does
not set `ARIS_DB_URL`.

## Branches

Existing work uses short prefixes such as `feat/…` and `research/…` when the
change is non-trivial; otherwise a clear branch name is enough.
