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

`static/dsh-index.json` is a **format 1** document. The rules come from
`@deepseek-ai/dsh-plugin-market-index` in the DSH bundle (`parseMarketIndex`);
`scripts/validate_index.py` reimplements them, so a document that passes locally
is not rejected with "not in a valid format".

```jsonc
{
  "format": 1,
  "title": "EXTREME RUSSIAN DSH FANDOM",   // a brand: one string for every language
  "description": { "en": "…", "ru": "…" },
  "metadata": {
    "categories": { "dev": { "title": { "en": "Development", "ru": "Разработка" } } },
    "labels":     { "ru":  { "title": "Русский" } },
    "sortKeys":   {}
  },
  "plugins": [{
    "name": "dsh-github-cli",       // npm package name, unique in the index
    "title": "GitHub CLI",
    "description": { "en": "…", "ru": "…" },
    "icon": "icons/plugins/dsh-github-cli.svg",
    "author": "…",
    "homepage": "…",
    "repository": { "url": "https://github.com/org/repo" },
    "metadata": { "category": "dev", "keywords": [], "labels": ["ru"] },
    "versions": [{
      "version": "0.2.0",
      "publishTimestamp": 1793878451,
      "source": { "type": "git", "url": "https://github.com/org/repo", "commit": "<sha>" },
      "engines": { "dsh": ">=0.9" }   // optional
    }]
  }]
}
```

What the validator actually enforces, and what is easy to get wrong:

- `format` is mandatory and must be `1`; plugins live in **`plugins`**, not
  `entries`;
- the file has **no** `install`, `defaultVersion`, `installation` or
  `compatibility` — DSH derives them from `source.commit` and builds the pnpm
  spec itself (`git+https://github.com/org/repo.git#<commit>`);
- `title` is required; a localized string is either a plain string or an object
  that **must** contain `en`;
- `metadata.category` and every id in `metadata.labels` must be declared in the
  top-level `metadata` block;
- `version` is an exact SemVer, `publishTimestamp` is integer Unix seconds below
  10^11;
- `source.type: "git"` requires a canonical https URL with at least two path
  segments and a lowercase 40-hex `commit`;
- `icon` may be relative (resolved against the index URL) or a `data:` URL up to
  32 KiB decoded;
- `homepage` may carry `#readme` — unlike repository URLs, its fragment is kept.
