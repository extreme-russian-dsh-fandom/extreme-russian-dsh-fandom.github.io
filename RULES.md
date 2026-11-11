# Publication rules

The catalog is not "everything in the organization": it is an explicit list in
`registry.toml`. The checks below are what the script runs over every candidate.
An entry without `status = "published"` never reaches the catalog, but it stays
in the report.

## Checks

| # | Rule | What it filters out in practice |
|---|---|---|
| 1 | repository is public, not archived, not a fork | `EDSH` (a fork of `ECC`) |
| 2 | the root has a `package.json` that parses and contains a `dsh` object | `EDSH` (its `dsh` lives in `.dsh/package.json`), `.github` |
| 3 | the file referenced by `dsh.bundle.patch` exists | broken bundles |
| 4 | the repository has at least one commit | empty repositories |
| 5 | the repository name starts with `dsh-` (or `allow_name = true`) | `clanker-playground`, stray repositories that happen to have a `dsh` field |
| 6 | `package.json` has a `version` | unfinished repositories |
| 7 | the repository is listed in `registry.toml` with `status = "published"` | everything else — publishing is a deliberate act |

Rules 1–6 produce the candidate list, rule 7 turns it into a catalog. The script
prints a report for every repository in the organization, so a new plugin shows
up as `candidate` instead of disappearing silently.

## Where each field comes from

Mechanical (never typed by hand):

- `version` — `package.json`;
- `commit` — the tag's commit when the repository has tags, otherwise the branch
  head, full 40-character SHA;
- `publishTimestamp` — the date of that commit, unix seconds;
- `install.spec` — `github:org/repo#<tag>` when a tag exists, otherwise
  `github:org/repo#<sha>`, so a human sees the version they can recognise;
- `icon` — `icon.svg` in the repository root;
- `keywords` — `keywords` from `package.json`;
- `engines.dsh` — `engines.dsh` from `package.json`, when present;
- label `ru` — added when the repository has `README.ru.md`.

Editorial (`registry.toml`):

- `summary` (English) and `summary_ru` — card text; a missing `summary_ru` falls
  back to `summary`, a missing `summary` falls back to the `package.json`
  description;
- `category` — an id from `[categories]`, with Russian captions in
  `[categories_ru]`; the localized caption is also the taxonomy term, so
  `/categories/development/` comes from the same table;
- `order`, `requires`.

## Generated files

For every published plugin, in both site languages:

```
content/plugins/<repo>/index.md      English (default language, no suffix)
content/plugins/<repo>/index.ru.md   Russian
```

MCP servers go to `content/servers/<repo>/` the same way. Icons land in
`static/icons/plugins/<repo>.svg`, the index in `static/dsh-index.json`.

## Index format

`static/dsh-index.json` is the document DSH reads in the Discover tab. The schema
was recovered from the DSH bundle (the `pluginMarket` zod schemas), so the field
names are exactly what the client expects:

```jsonc
{
  "title": { "en": "DSH plugins", "ru": "Плагины DSH" },
  "description": { "en": "…", "ru": "…" },
  "metadata": {
    "categories": { "dev": { "title": { "en": "Development", "ru": "Разработка" } } },
    "labels":     { "ru":  { "title": "Русский" } },
    "sortKeys":   {}
  },
  "entries": [{
    "name": "dsh-github-cli",       // unique identifier inside the index
    "title": "GitHub CLI",
    "description": { "en": "…", "ru": "…" },
    "icon": "icons/plugins/dsh-github-cli.svg",
    "author": "…",
    "homepage": "…",
    "repository": { "url": "https://github.com/…" },
    "defaultVersion": "0.2.0",
    "metadata": { "category": "dev", "keywords": [], "labels": ["ru"], "sortKeys": {} },
    "versions": [{
      "version": "0.2.0",
      "publishTimestamp": 1793878451,
      "install": { "spec": "github:org/repo#<sha>" },
      "source": { "type": "git", "url": "https://github.com/org/repo", "commit": "<sha>" },
      "engines": { "dsh": ">=0.9" }   // optional
    }]
  }]
}
```

What matters from the schema:

- `install.spec` is the string handed to `pnpm add`; `github:org/repo#<commit>`
  pins the installation to the same commit recorded in `source.commit`;
- `source.url` carries no credentials, query or fragment;
- `source.commit` is lowercase 40-hex;
- `icon` may be relative, it is resolved against the index URL;
- a localized string is either a plain string or an object that **must** contain
  `en` (`{"en": "…", "ru": "…"}`).
