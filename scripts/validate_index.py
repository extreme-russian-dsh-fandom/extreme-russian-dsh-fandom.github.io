#!/usr/bin/env python3
"""Validate static/dsh-index.json before it is deployed.

The schema comes from the `pluginMarket` zod definitions in the DSH bundle, so
the checks here are the ones that would make DSH reject the document or install
the wrong thing. Run it locally with the same command CI uses:

    python scripts/validate_index.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "static" / "dsh-index.json"

SHA = re.compile(r"[0-9a-f]{40}")


def fail(message: str) -> None:
    print(f"invalid index: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_entry(entry: dict) -> None:
    name = entry.get("name")
    if not name:
        fail("an entry has no name")

    versions = entry.get("versions") or []
    if not versions:
        fail(f"{name}: no versions")
    if entry.get("defaultVersion") != versions[0]["version"]:
        fail(f"{name}: defaultVersion does not point at the first version")

    for version in versions:
        source = version.get("source") or {}
        if source.get("type") != "git":
            fail(f"{name}: unsupported source type {source.get('type')!r}")

        url = source.get("url", "")
        if not url.startswith("https://"):
            fail(f"{name}: source url is not https")
        if "@" in url.split("//", 1)[-1] or "?" in url or "#" in url:
            fail(f"{name}: source url carries credentials, query or fragment")

        commit = source.get("commit", "")
        if not SHA.fullmatch(commit):
            fail(f"{name}: commit is not a lowercase 40-hex SHA")

        spec = (version.get("install") or {}).get("spec", "")
        if not spec.startswith("github:"):
            fail(f"{name}: install spec is not a github: address")

        ref = spec.rsplit("#", 1)[-1] if "#" in spec else ""
        if not ref:
            fail(f"{name}: install spec is not pinned to a revision")
        # A tag is a valid pin; a 40-hex ref has to be the recorded commit.
        if SHA.fullmatch(ref) and ref != commit:
            fail(f"{name}: install spec pins {ref[:8]}, source.commit is {commit[:8]}")

    metadata = entry.get("metadata") or {}
    if "labels" not in metadata or "keywords" not in metadata:
        fail(f"{name}: metadata lacks labels or keywords")


def main() -> int:
    if not INDEX.exists():
        fail(f"{INDEX} does not exist; run scripts/build_index.py first")

    document = json.loads(INDEX.read_text(encoding="utf-8"))
    entries = document.get("entries") or []
    if not entries:
        fail("the index has no entries")

    for entry in entries:
        check_entry(entry)

    print(f"{len(entries)} plugins in the index, schema checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
