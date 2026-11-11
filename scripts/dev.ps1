# Regenerate the catalog data and start the live server.
#
# `zola serve` rebuilds content/ and templates, but it never runs the generator:
# a new tag, a registry edit or a fresh plugin only shows up after this script
# (or a bare `python scripts/build_index.py`) has run.
#
#   pwsh -File scripts/dev.ps1                 regenerate, then serve
#   pwsh -File scripts/dev.ps1 -BuildOnly      regenerate only (server running)

param(
    [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'

# Interpreter candidates, in the order they are tried. A bare `python3` on
# Windows can be a Store stub that prints a banner and exits, so each candidate
# has to prove it is Python 3.11+ before it is used.
function Resolve-Python {
    foreach ($candidate in @(@('python'), @('python3'), @('py', '-3'))) {
        $exe = $candidate[0]
        $rest = if ($candidate.Length -gt 1) { $candidate[1..($candidate.Length - 1)] } else { @() }

        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
            continue
        }

        & $exe @rest -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Exe = $exe; Args = $rest }
        }
    }
    return $null
}

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $python = Resolve-Python
    if (-not $python) {
        throw 'no working Python 3.11+ found in PATH (tried python, python3, py -3)'
    }

    $label = (@($python.Exe) + @($python.Args)) -join ' '
    Write-Host "dev.ps1: using $label"

    & $python.Exe @($python.Args) scripts/build_index.py
    if ($LASTEXITCODE -ne 0) {
        throw "scripts/build_index.py failed with exit code $LASTEXITCODE"
    }

    if ($BuildOnly) {
        return
    }

    if (-not (Get-Command zola -ErrorAction SilentlyContinue)) {
        throw 'zola not found in PATH'
    }

    Write-Host 'dev.ps1: starting zola serve'
    zola serve
}
finally {
    Pop-Location
}
