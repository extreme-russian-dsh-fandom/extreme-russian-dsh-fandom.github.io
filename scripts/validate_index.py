#!/usr/bin/env python3
"""Validate static/dsh-index.json against the format DSH actually accepts.

The rules mirror `@deepseek-ai/dsh-plugin-market-index` (parseMarketIndex and its
helpers) from the DSH bundle, so a document that passes here is not rejected as
"not in a valid format". Errors name the same JSON paths DSH reports.

    python scripts/validate_index.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

INDEX = Path(__file__).resolve().parent.parent / "static" / "dsh-index.json"

LANGUAGE_ID = re.compile(r"^[a-z]{2,8}(?:-[a-z0-9]{1,8})*$")
PACKAGE_NAME = re.compile(r"^(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$")
PACKAGE_NAME_MAX_LENGTH = 214
NUMERIC = r"(?:0|[1-9]\d*)"
PRERELEASE_PART = rf"(?:{NUMERIC}|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
SEMVER = re.compile(
    rf"^{NUMERIC}\.{NUMERIC}\.{NUMERIC}"
    rf"(?:-{PRERELEASE_PART}(?:\.{PRERELEASE_PART})*)?"
    rf"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?$"
)
COMMIT = re.compile(r"^[0-9a-f]{40}$")
PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._@+-]+$")
MAX_PUBLISH_TIMESTAMP = 100_000_000_000


def fail(path: str, reason: str) -> None:
    print(f"invalid index: {path} {reason}", file=sys.stderr)
    raise SystemExit(1)


def string_at(value, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(path, "must be a string with a non-whitespace character")
    return value


def localized(value, path: str):
    if isinstance(value, str):
        return string_at(value, path)
    if not isinstance(value, dict):
        fail(path, "must be an object")
    if not value:
        fail(path, "must contain en")
    for language, member in value.items():
        if not LANGUAGE_ID.fullmatch(language):
            fail(f"{path}.{language}", "must be keyed by a lowercase language id")
        string_at(member, f"{path}.{language}")
    if "en" not in value:
        fail(path, "must contain en")
    return value


def declarations(value, path: str, *, sort_key: bool = False) -> dict:
    if not isinstance(value, dict):
        fail(path, "must be an object")
    for identifier, member in value.items():
        if identifier == "":
            fail(path, "must not declare an empty id")
        if not isinstance(member, dict):
            fail(f"{path}.{identifier}", "must be an object")
        localized(member.get("title"), f"{path}.{identifier}.title")
        if sort_key and member.get("order") not in ("asc", "desc"):
            fail(f"{path}.{identifier}.order", 'must be "asc" or "desc"')
    return value


def http_url(value, path: str, *, canonical: bool = False) -> str:
    text = string_at(value, path)
    parts = urlsplit(text)
    if parts.scheme not in ("https", "http"):
        fail(path, "must use https: or http:")
    if parts.username or parts.password:
        fail(path, "must not contain credentials")
    if parts.query or parts.fragment:
        fail(path, "must not contain a query or fragment")
    if canonical and parts.scheme != "https":
        fail(path, "must use https:")
    if canonical and len([s for s in parts.path.split("/") if s]) < 2:
        fail(path, "must name a repository with at least two path segments")
    return text


def homepage_url(value, path: str) -> str:
    """Absolute http(s) URL. Fragments and queries are allowed: npm homepages
    often carry `#readme`."""
    text = string_at(value, path)
    if urlsplit(text).scheme not in ("https", "http"):
        fail(path, "must use https: or http:")
    return text


def check_source(value, path: str) -> None:
    if not isinstance(value, dict):
        fail(path, "must be an object")
    kind = value.get("type")
    if kind == "npm":
        if "registry" in value:
            http_url(value["registry"], f"{path}.registry")
        return
    if kind != "git":
        fail(f"{path}.type", 'must be "npm" or "git"')

    commit = string_at(value.get("commit"), f"{path}.commit")
    if not COMMIT.fullmatch(commit):
        fail(f"{path}.commit", "must be a lowercase 40-hex-digit commit SHA")
    http_url(value.get("url"), f"{path}.url", canonical=True)
    if "path" in value:
        directory = string_at(value["path"], f"{path}.path")
        if any(segment in ("", ".", "..") or not PATH_SEGMENT.fullmatch(segment)
               for segment in directory.split("/")):
            fail(f"{path}.path", "must be a relative directory without . or .. segments")


def check_version(value, path: str) -> str:
    if not isinstance(value, dict):
        fail(path, "must be an object")

    version = string_at(value.get("version"), f"{path}.version")
    if not SEMVER.fullmatch(version):
        fail(f"{path}.version", "must be an exact SemVer version")

    timestamp = value.get("publishTimestamp")
    if (
        not isinstance(timestamp, int)
        or isinstance(timestamp, bool)
        or not 0 <= timestamp < MAX_PUBLISH_TIMESTAMP
    ):
        fail(f"{path}.publishTimestamp", "must be integer Unix seconds in [0, 10^11)")

    check_source(value.get("source"), f"{path}.source")

    engines = value.get("engines")
    if engines is not None:
        if not isinstance(engines, dict):
            fail(f"{path}.engines", "must be an object")
        if "dsh" in engines:
            string_at(engines["dsh"], f"{path}.engines.dsh")
    return version


def check_metadata(value, path: str, categories: dict, labels: dict) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        fail(path, "must be an object")

    if "category" in value:
        category = string_at(value["category"], f"{path}.category")
        if category not in categories:
            fail(f"{path}.category", f"references undeclared id {category!r}")

    keywords = value.get("keywords", [])
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        fail(f"{path}.keywords", "must be an array of strings")

    entry_labels = value.get("labels", [])
    if not isinstance(entry_labels, list):
        fail(f"{path}.labels", "must be an array")
    for position, label in enumerate(entry_labels):
        if string_at(label, f"{path}.labels[{position}]") not in labels:
            fail(f"{path}.labels[{position}]", f"references undeclared id {label!r}")
    if len(set(entry_labels)) != len(entry_labels):
        fail(f"{path}.labels", "must not repeat a label")


def check_plugin(value, path: str, categories: dict, labels: dict) -> str:
    if not isinstance(value, dict):
        fail(path, "must be an object")

    name = string_at(value.get("name"), f"{path}.name")
    if len(name) > PACKAGE_NAME_MAX_LENGTH or not PACKAGE_NAME.fullmatch(name):
        fail(f"{path}.name", "must be a valid npm package name")

    for key in ("title", "description"):
        if key in value:
            localized(value[key], f"{path}.{key}")
    if "author" in value:
        string_at(value["author"], f"{path}.author")
    if "homepage" in value:
        homepage_url(value["homepage"], f"{path}.homepage")
    if "repository" in value:
        repository = value["repository"]
        if not isinstance(repository, dict):
            fail(f"{path}.repository", "must be an object")
        http_url(repository.get("url"), f"{path}.repository.url")

    check_metadata(value.get("metadata"), f"{path}.metadata", categories, labels)

    versions = value.get("versions")
    if not isinstance(versions, list) or not versions:
        fail(f"{path}.versions", "must be a non-empty array")
    seen: set[str] = set()
    for position, member in enumerate(versions):
        at = f"{path}.versions[{position}]"
        parsed = check_version(member, at)
        if parsed in seen:
            fail(f"{at}.version", f"duplicates {parsed}")
        seen.add(parsed)
    return name


def main() -> int:
    if not INDEX.exists():
        fail(str(INDEX), "does not exist; run scripts/build_index.py first")

    document = json.loads(INDEX.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        fail("$", "must be an object")

    if document.get("format") != 1:
        fail("$.format", "must be 1")

    localized(document.get("title"), "$.title")
    if "description" in document:
        localized(document["description"], "$.description")

    metadata = document.get("metadata") or {}
    if not isinstance(metadata, dict):
        fail("$.metadata", "must be an object")
    categories = declarations(metadata.get("categories", {}), "$.metadata.categories")
    labels = declarations(metadata.get("labels", {}), "$.metadata.labels")
    declarations(metadata.get("sortKeys", {}), "$.metadata.sortKeys", sort_key=True)

    plugins = document.get("plugins")
    if not isinstance(plugins, list):
        fail("$.plugins", "must be an array")

    names: set[str] = set()
    for position, member in enumerate(plugins):
        name = check_plugin(member, f"$.plugins[{position}]", categories, labels)
        if name in names:
            fail(f"$.plugins[{position}].name", f"duplicates {name}")
        names.add(name)

    print(f"format 1, {len(plugins)} plugins, schema checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
