#!/usr/bin/env python3
"""Build the DSH plugin catalog from the organization's public repositories.

Reads `registry.toml`, checks every repository against the rules in RULES.md and
generates, for both site languages:

  content/plugins/<repo>/index.md       plugin page, default language (ru)
  content/plugins/<repo>/index.en.md    plugin page, English
  content/servers/<repo>/...            same, for MCP servers (separate section)
  static/icons/plugins/<repo>.svg       icon copied from the repository
  static/dsh-index.json                 index document for DSH "Discover"

Standard library only (Python 3.11+). Network: GitHub REST (repository list,
last commit) and raw.githubusercontent.com (file contents). A token is optional.

    python scripts/build_index.py            # build
    python scripts/build_index.py --check    # report only, write nothing
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.toml"
CONTENT = ROOT / "content"
STATIC = ROOT / "static"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "ru")


# --------------------------------------------------------------------------
# network


def _get(url: str, *, token: str = "", accept: str = "application/vnd.github+json") -> bytes:
    headers = {"User-Agent": "dsh-fandom-index", "Accept": accept}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def api(path: str):
    """GET a GitHub API path; retry anonymously if the token is rejected."""
    url = API + path
    try:
        return json.loads(_get(url, token=TOKEN))
    except urllib.error.HTTPError as error:
        if TOKEN and error.code in (401, 403):
            print(f"  ! token rejected ({error.code}), retrying anonymously", file=sys.stderr)
            return json.loads(_get(url))
        raise


def raw(org: str, repo: str, branch: str, path: str) -> str | None:
    """Return file contents from a branch, or None when the file is absent."""
    url = f"{RAW}/{org}/{repo}/{branch}/{path}"
    try:
        return _get(url, accept="text/plain").decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def parse_moment(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def head_commit(org: str, repo: str, branch: str) -> str:
    """SHA of the branch head, used to pin an installation."""
    commits = api(f"/repos/{org}/{repo}/commits?sha={branch}&per_page=1")
    if not commits:
        raise LookupError("no commits")
    return commits[0]["sha"]


def version_moment(org: str, repo: str, branch: str) -> tuple[int, str, str | None, str]:
    """When the current version appeared, which signal said so, its tag and commit.

    A tag is an explicit release marker, so it wins; without tags the branch head
    is the only thing left. A new tag automatically takes over once it lands.
    """
    tags = api(f"/repos/{org}/{repo}/tags?per_page=1")
    if tags:
        tag_sha = tags[0]["commit"]["sha"]
        commit = api(f"/repos/{org}/{repo}/commits/{tag_sha}")
        return (
            parse_moment(commit["commit"]["committer"]["date"]),
            "tag",
            tags[0]["name"],
            tag_sha,
        )

    head = api(f"/repos/{org}/{repo}/commits?sha={branch}&per_page=1")
    if not head:
        raise LookupError("no commits")
    return (
        parse_moment(head[0]["commit"]["committer"]["date"]),
        "head",
        None,
        head[0]["sha"],
    )


# --------------------------------------------------------------------------
# repository parsing


def pick_strings(*values) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def author_of(package: dict) -> str | None:
    author = package.get("author")
    if isinstance(author, str):
        return author
    if isinstance(author, dict):
        return pick_strings(author.get("name"))
    return None


def check(repo: dict, package: dict | None, patch: str | None, name: str, spec: dict) -> str | None:
    """Return the rejection reason, or None when the repository qualifies."""
    if repo.get("archived"):
        return "archived"
    if repo.get("fork"):
        return "fork"
    if package is None:
        return "no package.json"
    if not isinstance(package.get("dsh"), dict):
        return "package.json has no dsh object"
    patch_path = (package.get("dsh") or {}).get("bundle", {}).get("patch")
    if not patch_path:
        return "dsh.bundle.patch is not set"
    if patch is None:
        return f"missing {patch_path}"
    if not pick_strings(package.get("version")):
        return "no version"
    if not name.startswith("dsh-") and not spec.get("allow_name"):
        return "no dsh- prefix"
    return None


def toml_string(value: str) -> str:
    """JSON escaping is a valid subset of TOML basic strings."""
    return json.dumps(value, ensure_ascii=False)


def toml_array(values: list[str]) -> str:
    return "[" + ", ".join(toml_string(v) for v in values) + "]"


# --------------------------------------------------------------------------
# page generation

TEXT = {
    "ru": {
        "sources": "Исходники:",
        "requires_dsh": "Требует DSH",
        "cli_heading": "Установка через CLI",
        "desktop_heading": "Установка в DSH Desktop",
        "catalog_heading": "Установка из каталога",
        "catalog_intro": (
            "Чтобы плагины появлялись во вкладке **Discover**, DSH должен знать адрес "
            "индекса. Каталог публикуется как один файл:"
        ),
        "server_note": (
            "Это MCP-сервер, а не плагин DSH: отдельным бандлом он не ставится.\n"
            "Подключите его как MCP-сервер, а обвязку для DSH ищите в каталоге плагинов."
        ),
    },
    "en": {
        "sources": "Sources:",
        "requires_dsh": "Requires DSH",
        "cli_heading": "Install via CLI",
        "desktop_heading": "Install in DSH Desktop",
        "catalog_heading": "Install from the catalog",
        "catalog_intro": (
            "For plugins to show up under **Discover**, DSH has to know the index URL. "
            "The catalog is published as a single file:"
        ),
        "server_note": (
            "This is an MCP server, not a DSH plugin: it does not install as a bundle.\n"
            "Connect it as an MCP server; the DSH wrapper lives in the plugin catalog."
        ),
    },
}

# Step-by-step screenshots live in static/guide. Each step is
# (image file, ru text, en text); a missing image drops the picture but keeps the
# text, so the guide degrades instead of showing a broken image.
DESKTOP_STEPS = [
    (
        "desktop-install-00.png",
        "Откройте **Plugins** в боковой панели DSH.",
        "Open **Plugins** in the DSH sidebar.",
    ),
    (
        "desktop-install-01.png",
        "Нажмите **Add plugin** в правом верхнем углу.",
        "Press **Add plugin** in the top right corner.",
    ),
    (
        "desktop-install-02.png",
        "Вставьте адрес плагина из подзаголовка и нажмите **Install**.",
        "Paste the plugin address from the subtitle and press **Install**.",
    ),
]

CATALOG_SETUP_IMAGES = ["desktop-index-00.png", "desktop-index-01.png"]
CATALOG_SETUP_TEXT = (
    "Откройте **Settings → Experimental plugins**, разверните список целиком "
    "и включите **Custom plugin indexes**.",
    "Open **Settings → Experimental plugins**, expand the whole list and turn on "
    "**Custom plugin indexes**.",
)

# The second step has two variants: an empty Discover tab and one that already
# holds a source. Both are shown, each with its own condition.
CATALOG_OPEN_VARIANTS = [
    (
        "desktop-index-02-A.png",
        "источников ещё нет — **Add index source**.",
        "no sources yet — **Add index source**.",
    ),
    (
        "desktop-index-02-B.png",
        "источник уже есть — список источников → **Manage index sources…**.",
        "a source already exists — the source list → **Manage index sources…**.",
    ),
]

CATALOG_ADD_STEP = (
    "desktop-index-03.png",
    "Вставьте тот же адрес в поле и нажмите **Add**.",
    "Paste the same address into the field and press **Add**.",
)


def figure(image: str, language: str, caption: str | None = None) -> str:
    """Raw <figure> for a screenshot from static/guide, or "" when it is absent."""
    if not (STATIC / "guide" / image).exists():
        return ""
    alt = {
        "ru": "Скриншот шага установки",
        "en": "Installation step screenshot",
    }[language]
    caption_html = f"\n  <figcaption>{caption}</figcaption>" if caption else ""
    return (
        "<figure>\n"
        f'  <img src="/guide/{image}" alt="{alt}" loading="lazy">'
        f"{caption_html}\n"
        "</figure>\n"
    )


def step(number: int, text: str, image: str, language: str) -> str:
    return f"**{number}.** {text}\n\n{figure(image, language)}"


def page_body(entry: dict, kind: str, language: str) -> str:
    text = TEXT[language]
    lines: list[str] = []

    if kind != "plugin":
        lines += [text["sources"] + f" <{entry['repository_url']}>", ""]
        lines += [text["server_note"], ""]
        if entry.get("engines_dsh"):
            lines += [f"{text['requires_dsh']} `{entry['engines_dsh']}`", ""]
        return "\n".join(lines)

    # The install spec doubles as the page subtitle: it is the one string the
    # user has to copy, and it works in both the CLI and the Desktop dialog.
    # The repository link sits right next to it — putting it at the bottom of a
    # page with three installation sections means scrolling past everything.
    lines += [f"`{entry['install_spec']}`", ""]
    lines += [text["sources"] + f" <{entry['repository_url']}>", ""]

    lines += [
        f"## {text['cli_heading']}",
        "",
        "```bash",
        f"dsh plugin add {entry['install_spec']}",
        "```",
        "",
    ]

    lines += [f"## {text['desktop_heading']}", ""]
    for number, (image, ru, en) in enumerate(DESKTOP_STEPS, start=1):
        lines += [step(number, ru if language == "ru" else en, image, language), ""]

    lines += [
        f"## {text['catalog_heading']}",
        "",
        text["catalog_intro"],
        "",
        "```",
        entry["index_url"],
        "```",
        "",
    ]

    setup_text = CATALOG_SETUP_TEXT[0] if language == "ru" else CATALOG_SETUP_TEXT[1]
    setup_figures = "".join(figure(image, language) for image in CATALOG_SETUP_IMAGES)
    lines += [f"**1.** {setup_text}", "", setup_figures, ""]

    variants = []
    for index, (image, ru, en) in enumerate(CATALOG_OPEN_VARIANTS):
        rendered = figure(image, language)
        if not rendered:
            continue
        label = ("Вариант", "A") if language == "ru" else ("Option", "A")
        letter = "AB"[index]
        heading = f"**{label[0]} {letter}**"
        variants.append(f"{heading} — {ru if language == 'ru' else en}\n\n{rendered}")
    if variants:
        lines += ["**2.** " + ("Откройте **Plugins → Discover**. Дальше — по ситуации:"
                              if language == "ru"
                              else "Open **Plugins → Discover**. Then pick your case:"), ""]
        for variant in variants:
            lines += [variant, ""]

    add_image, add_ru, add_en = CATALOG_ADD_STEP
    lines += [step(3, add_ru if language == "ru" else add_en, add_image, language), ""]

    if entry.get("engines_dsh"):
        lines += [f"{text['requires_dsh']} `{entry['engines_dsh']}`", ""]

    return "\n".join(lines)


def page_front_matter(entry: dict, language: str) -> str:
    lines = [
        "+++",
        f"title = {toml_string(entry['title'])}",
        f"description = {toml_string(entry['description'][language])}",
        f"weight = {entry['order']}",
        "",
        "[taxonomies]",
        # The taxonomy term is the localized category caption, so /categories/dev/
        # becomes /categories/development/ and displays without a lookup table.
        f"categories = {toml_array([entry['category_title'][language]])}",
        "",
        "[extra]",
        f"github = {toml_string(entry['repository_url'])}",
        f"remote_image = {toml_string(entry['icon_url'])}",
        f"category = {toml_string(entry['category'])}",
        f"category_title = {toml_string(entry['category_title'][language])}",
        f"version = {toml_string(entry['version'])}",
        f"commit = {toml_string(entry['commit'])}",
        f"install = {toml_string(entry['install_spec'])}",
        f"updated = {toml_string(entry['updated'])}",
        # Sort key for "latest plugins": date first, then the catalog order
        # ascending once the list is reversed. Tera can only sort on one key, so
        # the order is folded into the date string instead of a second pass.
        f"recency = {toml_string(entry['recency'])}",
    ]
    if entry.get("tag"):
        lines.append(f"tag = {toml_string(entry['tag'])}")
    if entry.get("requires"):
        lines.append(f"requires = {toml_array(entry['requires'])}")
    lines.append("+++")
    return "\n".join(lines)


def page_path(directory: Path, language: str) -> Path:
    if language == DEFAULT_LANGUAGE:
        return directory / "index.md"
    return directory / f"index.{language}.md"


def write_page(directory: Path, entry: dict, kind: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for language in LANGUAGES:
        body = page_front_matter(entry, language) + "\n\n" + page_body(entry, kind, language)
        page_path(directory, language).write_text(body, encoding="utf-8")
    # The default language has no suffix, so drop leftovers such as index.en.md
    # (right after a default-language switch) and pages of retired languages.
    for stale in directory.glob("index.*.md"):
        suffix = stale.name[len("index.") : -len(".md")]
        if suffix == DEFAULT_LANGUAGE or suffix not in LANGUAGES:
            stale.unlink()


def prune(keep: set[str], directory: Path) -> None:
    """Remove previously generated directories that are no longer in the registry."""
    if not directory.exists():
        return
    for child in directory.iterdir():
        if child.is_dir() and child.name not in keep:
            shutil.rmtree(child)


# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report only, write nothing")
    options = parser.parse_args()

    registry = tomllib.loads(REGISTRY.read_text(encoding="utf-8"))
    site = registry["site"]
    org = site["org"]
    base_url = site["base_url"].rstrip("/")
    index_url = f"{base_url}/dsh-index.json"
    categories = registry.get("categories", {})
    declared_labels = registry.get("labels", {})

    plugins = {item["repo"]: item for item in registry.get("plugin", [])}
    servers = {item["repo"]: item for item in registry.get("server", [])}
    excluded = {item["repo"]: item for item in registry.get("excluded", [])}
    wanted = {**plugins, **servers}

    print(f"org: {org}")
    repositories = api(f"/orgs/{org}/repos?per_page=100&type=public")
    print(f"public repositories: {len(repositories)}\n")

    built_plugins: list[dict] = []
    built_servers: list[dict] = []
    report: list[tuple[str, str, str]] = []
    failures: list[str] = []

    for repo in sorted(repositories, key=lambda item: item["name"].lower()):
        name = repo["name"]
        branch = repo.get("default_branch") or "main"

        if name in excluded:
            report.append((name, "excluded", excluded[name].get("reason", "")))
            continue

        spec = wanted.get(name)
        if spec is None:
            report.append((name, "candidate", "not in registry.toml"))
            continue

        status = spec.get("status", "published")
        kind = "plugin" if name in plugins else "server"

        try:
            sha = head_commit(org, name, branch)
            timestamp, moment_kind, tag, version_sha = version_moment(org, name, branch)
        except LookupError:
            report.append((name, "pending", spec.get("note", "no commits")))
            if status == "published":
                failures.append(f"{name}: no commits, but registry says published")
            continue

        package_text = raw(org, name, branch, "package.json")
        try:
            package = json.loads(package_text) if package_text else None
        except json.JSONDecodeError:
            package = None

        patch_path = ((package or {}).get("dsh") or {}).get("bundle", {}).get("patch")
        patch = raw(org, name, branch, patch_path.lstrip("./")) if patch_path else None

        problem = check(repo, package, patch, name, spec)
        if problem:
            report.append((name, "rejected", problem))
            if status == "published":
                failures.append(f"{name}: {problem}")
            continue

        if status != "published":
            report.append((name, "pending", spec.get("note", f"status = {status}")))
            continue

        version = pick_strings(package.get("version"))
        readme_ru = raw(org, name, branch, "README.ru.md")
        labels = [label for label in spec.get("labels", []) if label in declared_labels]
        if readme_ru is not None and "ru" in declared_labels:
            labels = sorted(set(labels) | {"ru"})
        labels = [label for label in labels if label in declared_labels]

        category = spec.get("category", "misc")
        keywords = [k for k in package.get("keywords", []) if isinstance(k, str)][:12]
        engines_dsh = pick_strings((package.get("engines") or {}).get("dsh"))

        fallback = pick_strings(package.get("description")) or name
        description = {
            "ru": pick_strings(spec.get("summary_ru"), spec.get("summary"), fallback),
            "en": pick_strings(spec.get("summary"), fallback),
        }
        title = spec.get("title") or name.removeprefix("dsh-").replace("-", " ")
        category_title = {
            "ru": registry.get("categories_ru", {}).get(category, categories.get(category, category)),
            "en": categories.get(category, category),
        }

        icon_text = raw(org, name, branch, "icon.svg")
        icon_url = f"/icons/plugins/{name}.svg" if icon_text is not None else ""

        repository_url = f"https://github.com/{org}/{name}"
        updated = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")

        entry = {
            "repo": name,
            # DSH matches an installed bundle to a market entry by the package
            # name, not by the repository name, so the index must publish the
            # name the installed copy actually declares.
            "package_name": pick_strings(package.get("name")) or name,
            "kind": kind,
            "title": title,
            "description": description,
            "category": category,
            "category_title": category_title,
            "order": int(spec.get("order", 500)),
            "requires": spec.get("requires", []),
            "version": version,
            # With a tag the version is pinned by the tag name, which is what a
            # human would type; the commit behind it is still recorded exactly.
            "commit": version_sha,
            "tag": tag,
            "timestamp": timestamp,
            "updated": updated,
            "recency": f"{updated}-{9999 - int(spec.get('order', 500)):04d}",
            "repository_url": repository_url,
            "install_spec": (
                f"github:{org}/{name}#{tag}" if tag else f"github:{org}/{name}#{sha}"
            ),
            "index_url": index_url,
            "icon_url": icon_url,
            "icon_text": icon_text,
            "keywords": keywords,
            "engines_dsh": engines_dsh,
            "labels": labels,
            "author": author_of(package),
            "homepage": pick_strings(package.get("homepage")),
        }
        (built_plugins if kind == "plugin" else built_servers).append(entry)
        note = f"v{version} @ {sha[:8]} ({kind}, date from {moment_kind})"
        if not spec.get("summary"):
            note += ", summary missing — package description used"
        if entry["package_name"] != name:
            note += f", index name is {entry['package_name']} (package.json), repo is {name}"
        report.append((name, "published", note))

    # ---- write ------------------------------------------------------------

    built_plugins.sort(key=lambda item: (item["order"], item["repo"]))
    built_servers.sort(key=lambda item: (item["order"], item["repo"]))

    if not options.check:
        for section, entries in (("plugins", built_plugins), ("servers", built_servers)):
            target = CONTENT / section
            prune({entry["repo"] for entry in entries}, target)
            for entry in entries:
                write_page(target / entry["repo"], entry, entry["kind"])

        icons = STATIC / "icons" / "plugins"
        if icons.exists():
            shutil.rmtree(icons)
        icons.mkdir(parents=True, exist_ok=True)
        for entry in built_plugins + built_servers:
            if entry["icon_text"] is not None:
                (icons / f"{entry['repo']}.svg").write_text(entry["icon_text"], encoding="utf-8")

        # Format 1, as validated by @deepseek-ai/dsh-plugin-market-index:
        # `format` first, plugins under `plugins`, and no install/defaultVersion —
        # DSH derives both from `source.commit` itself.
        document = {
            "format": 1,
            # A brand name, so it is the same in every language.
            "title": site["index_title"],
            # Localized strings may be an object, but `en` is mandatory there.
            "description": {"en": site["index_description"], "ru": site["index_description_ru"]},
            "metadata": {
                "categories": {
                    key: {
                        "title": {
                            "en": value,
                            "ru": registry.get("categories_ru", {}).get(key, value),
                        }
                    }
                    for key, value in categories.items()
                },
                "labels": {key: {"title": value} for key, value in declared_labels.items()},
                "sortKeys": {},
            },
            "plugins": [
                {
                    "name": entry["package_name"],
                    "title": entry["title"],
                    "description": {"en": entry["description"]["en"], "ru": entry["description"]["ru"]},
                    "icon": entry["icon_url"].lstrip("/") or None,
                    "author": entry["author"],
                    "homepage": entry["homepage"],
                    "repository": {"url": entry["repository_url"]},
                    "metadata": {
                        "category": entry["category"],
                        "keywords": entry["keywords"],
                        "labels": entry["labels"],
                    },
                    "versions": [
                        {
                            "version": entry["version"],
                            "publishTimestamp": entry["timestamp"],
                            "source": {
                                "type": "git",
                                "url": entry["repository_url"],
                                "commit": entry["commit"],
                            },
                            **(
                                {"engines": {"dsh": entry["engines_dsh"]}}
                                if entry["engines_dsh"]
                                else {}
                            ),
                        }
                    ],
                }
                for entry in built_plugins
            ],
        }
        for entry in document["plugins"]:
            for key in ("icon", "author", "homepage"):
                if entry[key] is None:
                    del entry[key]

        STATIC.mkdir(parents=True, exist_ok=True)
        (STATIC / "dsh-index.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # ---- report -----------------------------------------------------------

    width = max((len(name) for name, _, _ in report), default=10)
    print(f"{'repository'.ljust(width)}  {'status':<10}  note")
    for name, status, note in report:
        print(f"{name.ljust(width)}  {status:<10}  {note}")

    print(
        f"\nplugins in index: {len(built_plugins)}, "
        f"MCP servers: {len(built_servers)}, "
        f"file: {index_url}"
    )
    if options.check:
        print("--check: nothing written")
    if failures:
        print("\nfailures:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

