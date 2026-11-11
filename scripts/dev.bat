@echo off
rem Regenerate the catalog data and start the live server.
rem
rem `zola serve` rebuilds content/ and templates, but never runs the generator, so
rem a new tag, a registry edit or a fresh plugin only shows up after this script.
rem
rem   scripts\dev.bat                 regenerate, then serve
rem   scripts\dev.bat --build-only    regenerate only (server already running)

setlocal EnableExtensions
pushd "%~dp0.."

rem Interpreter candidates, in the order they are tried. A bare `python3` on
rem Windows can be a Store stub that prints a banner and exits, so each candidate
rem has to prove it is Python 3.11+ before it is used.
set "PYTHON="
for %%C in (python python3) do (
    if not defined PYTHON (
        where %%C >nul 2>&1 && set "PYTHON=%%C"
    )
)
if not defined PYTHON (
    where py >nul 2>&1 && set "PYTHON=py -3"
)
if not defined PYTHON (
    echo dev.bat: no Python found in PATH ^(tried python, python3, py^) 1>&2
    popd
    exit /b 1
)

%PYTHON% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo dev.bat: %PYTHON% is older than Python 3.11 1>&2
    popd
    exit /b 1
)

echo dev.bat: using %PYTHON%
%PYTHON% scripts\build_index.py
if errorlevel 1 (
    echo dev.bat: build_index.py failed 1>&2
    popd
    exit /b 1
)

if /i "%~1"=="--build-only" (
    popd
    exit /b 0
)

where zola >nul 2>&1 || (
    echo dev.bat: zola not found in PATH 1>&2
    popd
    exit /b 1
)

echo dev.bat: starting zola serve
zola serve
popd
