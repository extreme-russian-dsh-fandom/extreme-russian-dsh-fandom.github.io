# extreme-russian-dsh-fandom.github.io

Plugin showcase for DSH plus the machine-readable index for the **Discover** tab
in DeepSeek Harness.

- site: <https://extreme-russian-dsh-fandom.github.io> (English, default)
- Russian: <https://extreme-russian-dsh-fandom.github.io/ru/>
- index: <https://extreme-russian-dsh-fandom.github.io/dsh-index.json>

Stack: [Zola](https://www.getzola.org/) + [apollo](https://github.com/not-matthias/apollo)
theme (git submodule, pinned to an exact commit) + one dependency-free Python
script. Nothing is typed by hand except `registry.toml`.

## How it works

```
registry.toml                  <- the only hand-maintained file
scripts/build_index.py         <- GitHub API + raw -> pages and index
        |
        +- content/plugins/<repo>/index.md      plugin page, English
        +- content/plugins/<repo>/index.ru.md   plugin page, Russian
        +- content/servers/<repo>/...           MCP servers (own section)
        +- static/icons/plugins/<repo>.svg      icon copied from the repo
        +- static/dsh-index.json                index document for DSH
        |
        +- zola build -> public/ -> GitHub Pages
```

Everything generated is gitignored: the repository holds the registry, templates
and prose only. CI rebuilds the data on every deploy and once a day on a cron.

## Theme submodule

`.gitmodules` points at the upstream theme,
`https://github.com/not-matthias/apollo`, and the gitlink pins the tag
`v1.0.1` (`5d3ffce`). Two reasons for that exact pin:

- `v2.x` uses the new `{% component %}` template syntax and targets a newer Zola
  than the 0.22.1 this site builds with;
- the commit the personal site (`untodesu/website`) pins is no longer reachable
  from any branch upstream, so `git submodule update` cannot check it out.

```bash
git submodule update --init --recursive
```

Updating the theme is deliberate:

```bash
cd themes/apollo && git fetch --tags && git checkout v2.0.1 && cd ../..
git add themes/apollo && git commit -m "theme: bump apollo to v2.0.1"
```

Note that `v2.x` expects templates that do not exist in this site (its card
component, `apollo/` partials), so a bump means re-checking `templates/` and
`zola.toml` against the new layout.

## Adding or removing a plugin

Edit `registry.toml` only.

```toml
[[plugin]]
repo = "dsh-my-thing"          # repository name in the organization
title = "My Thing"             # card caption
category = "dev"               # id from [categories]; also the taxonomy term
order = 80                     # catalog order
summary = "One line, in English."
summary_ru = "Одной строкой, по-русски."
```

There are no free-form tags on purpose: with a handful of plugins a tag taxonomy
produces dozens of pages with one entry each, while categories group them. The
category doubles as the taxonomy term, so `/categories/development/` is generated
from the same `[categories]` table.

Nothing else is needed: version, commit, date, icon, links and `keywords` come
from the repository. A missing `summary` falls back to the `package.json`
description; a missing `summary_ru` falls back to `summary`.

Statuses: `published` (default), `pending` (known, not published, the reason goes
in `note`), `excluded` (deliberately not a plugin, the reason goes in `reason`).

The rules that make a repository a plugin at all are in [RULES.md](RULES.md), and
so is the index format.

## Locally

```bash
python3 scripts/build_index.py           # build the data (network required)
python3 scripts/build_index.py --check   # report only: who is published, who is not
python3 scripts/validate_index.py        # schema checks for static/dsh-index.json
zola serve                               # http://127.0.0.1:1111
zola build
```

`zola serve` rebuilds `content/` and templates but never runs the generator, so a
new tag, a registry edit or a new plugin only appears after `build_index.py` runs.
Three wrappers do both in one go, with a build-only mode for when the server is
already running:

```bash
scripts/dev.sh                  # Linux / macOS / Git Bash
scripts\dev.bat                 # Windows cmd
pwsh -File scripts/dev.ps1      # PowerShell
```

```bash
scripts/dev.sh --build-only
scripts\dev.bat --build-only
pwsh -File scripts/dev.ps1 -BuildOnly
```

PowerShell may refuse to run any `.ps1` under the default execution policy; then
either use `pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1` or just use the
`.bat`, which has no such restriction.

Each wrapper picks the first interpreter that actually runs Python 3.11+, trying
`python3`, `python` and `py -3`. On Windows `python3` is often the Microsoft Store
stub in `WindowsApps`, which prints a banner and exits — probing by running code
instead of by name is what keeps that from turning into a silent no-op.

`GITHUB_TOKEN` is optional locally: ten repositories fit in the anonymous rate
limit (60 requests per hour).

## Notes

- **Two languages.** English is the default and lives at the site root, Russian
  lives under `/ru/`. Zola cannot merge `extra` per language, so language-
  dependent values (`menu`) are keyed by language in `zola.toml` and selected in
  templates via `lang`. In content, the default language has no suffix:
  `index.md` is English, `index.ru.md` is Russian.
- **Fonts.** The theme ships Zed Text/Display and Space Grotesk, none of which
  have Cyrillic glyphs, so Russian fell back per glyph and looked ragged.
  `static/custom.css` replaces the theme's font variables with stacks that cover
  Cyrillic.
- **Install guide is generated per plugin.** Every plugin page starts with the
  `github:org/repo#<commit>` address, then three sections: CLI, DSH Desktop, and
  the catalog index. Screenshots come from `static/guide/` and are referenced by
  name; a missing file drops the picture and keeps the text, so the guide
  degrades instead of showing a broken image. The same text is mirrored in
  `content/install.md` / `content/install.ru.md`, which stays a hand-written
  overview.
- **Dates come from tags when they exist.** The version date is the latest tag's
  commit date; repositories without tags fall back to the branch head. The
  install spec always pins the head SHA, so a tag only changes the date shown and
  the order of "latest plugins" on the home page.
- **Search** is the theme's client-side search: `search_index.<lang>.js` is built
  for both languages.

## Layout

```
content/_index.md           home page (template templates/home.html)
content/plugins/_index.md   catalog section (template templates/plugins_list.html)
content/servers/_index.md   MCP servers section
content/install.md          how to install a plugin
templates/plugins_list.html section listing with compact cards
templates/macros/cards.html the card itself (icon avatar, name, summary, category)
templates/partials/nav.html theme nav plus the language switch
templates/home.html         home page
templates/taxonomy_*.html   tag pages (plugins have no dates)
registry.toml               registry
RULES.md                    publication rules and index format
scripts/build_index.py      the builder
```

The catalog does not use the theme's `cards.html`: that one reserves a media
banner per card, which turned a 40px icon into the loudest element on the page
and left iconless plugins as bare text. `templates/macros/cards.html` keeps the
icon as a small avatar, falls back to a letter avatar when a repository has no
`icon.svg`, and makes the whole card the link.
