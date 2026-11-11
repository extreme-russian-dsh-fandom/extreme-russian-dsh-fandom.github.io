+++
title = "How to install a plugin"
description = "Three routes: CLI, DSH Desktop and the catalog index"
+++

A plugin is a DSH bundle: a package with `cordis.patch.yml` that adds tools,
services or interface elements to the harness. There are three ways to install
it, and all of them end up with the same package.

Step-by-step screenshots live on every plugin page — the ready-to-paste address
of the form `github:org/repo#commit` is there too.

## 1. Via the CLI

```bash
dsh plugin add github:extreme-russian-dsh-fandom/dsh-github-cli
```

`dsh plugin add` accepts a package name with a version, a git address, a tarball
or an absolute path. The `github:org/repo` address installs the head of the
default branch; to pin an exact revision, append `#<commit>`.

## 2. Via DSH Desktop

**Plugins** in the sidebar → **Add plugin** → paste the address → **Install**.

## 3. From the catalog

For plugins to show up under **Discover**, DSH has to know the index URL — it is
a single file:

```
https://extreme-russian-dsh-fandom.github.io/dsh-index.json
```

The order:

1. **Settings → Experimental plugins** → turn on **Custom plugin indexes**
   (expand the whole list, the feature sits inside it).
2. **Plugins → Discover**:
   - no sources yet — **Add index source**;
   - a source already exists — the source list → **Manage index sources…**.
3. Paste the index address and press **Add**.

This path also gives you a compatibility check: DSH compares the plugin version
against your harness version and refuses a plugin that is known to be
incompatible.

The catalog is rebuilt once a day, so a brand-new release may not show up right
away. The refresh button in Discover re-reads the index immediately.

## Updating and removing

Install and remove plugins through the `dsh plugin` subcommands; the current list
is in `dsh plugin --help`, because it changes between versions. Under the hood
`dsh plugin` runs plain pnpm, so the profile directory stays an ordinary
`package.json` plus `pnpm-lock.yaml`, and a broken installation can always be
repaired by hand.

## When it does not install

- **`dsh: installation rejected`** — DSH rolled the installation back and
  restored `package.json` and `pnpm-lock.yaml`. The message usually names the
  cause; the full log is in the command output.
- **The plugin does not appear** — check that it is enabled in the profile:
  installing and activating are two separate steps.
- **The catalog cannot be read** — DSH expects an `http(s)` address without
  credentials or a `#` fragment. If the index returns 404, check the whole URL,
  including `/dsh-index.json`.
