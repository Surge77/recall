#!/usr/bin/env bash
#
# Recall installer.
#
# 1. verifies Python 3.11+
# 2. installs uv if it is missing (official upstream installer)
# 3. installs the `recall` CLI globally with `uv tool install`
# 4. wires the auto-capture shell hook
#
# Run from anywhere:  ./scripts/install.sh
#
set -euo pipefail

MIN_PY_MAJOR=3
MIN_PY_MINOR=11

err() { printf 'error: %s\n' "$1" >&2; exit 1; }
info() { printf '%s\n' "$1"; }

# --- 1. Python 3.11+ --------------------------------------------------------
command -v python3 >/dev/null 2>&1 || err "python3 not found; install Python 3.11+ first."
read -r py_major py_minor < <(python3 -c 'import sys; print(sys.version_info.major, sys.version_info.minor)')
if [ "$py_major" -lt "$MIN_PY_MAJOR" ] ||
   { [ "$py_major" -eq "$MIN_PY_MAJOR" ] && [ "$py_minor" -lt "$MIN_PY_MINOR" ]; }; then
    err "Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ required (found ${py_major}.${py_minor})."
fi
info "Python ${py_major}.${py_minor} OK."

# --- 2. uv ------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    info "uv not found; installing from astral.sh ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || err "uv install failed; see https://docs.astral.sh/uv/."
info "uv OK."

# --- 3. install the CLI globally (idempotent) -------------------------------
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
info "Installing recall from ${repo_root} ..."
uv tool install --force "$repo_root"

# --- 4. wire the shell hook -------------------------------------------------
recall install

info ""
info "Recall installed. Restart your terminal to activate auto-capture."
