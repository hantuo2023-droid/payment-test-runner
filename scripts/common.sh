#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
dc() { docker compose --project-directory "$ROOT" "$@"; }
require_docker() { command -v docker >/dev/null; docker compose version >/dev/null; }
