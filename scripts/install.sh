#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$(uname -s)" == Linux ]] || { echo 'Installer supports Linux only'; exit 1; }
[[ $EUID -eq 0 ]] || { echo 'Run installer with sudo'; exit 1; }
# Local: sudo bash scripts/install.sh
# Published installer: curl -fsSL YOUR_RAW_INSTALLER_URL | sudo PTR_REPO_URL=YOUR_GIT_URL bash
if [[ -f "$(dirname "${BASH_SOURCE[0]:-/dev/stdin}")/../compose.yaml" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
else
  : "${PTR_REPO_URL:?Provide PTR_REPO_URL pointing to your published repository}"
  ROOT="${PTR_INSTALL_DIR:-/opt/payment-test-runner}"
  [[ ! -e "$ROOT" ]] || { echo "Install directory already exists; use update.sh" >&2; exit 1; }
  command -v git >/dev/null || { apt-get update; apt-get install -y git; }
  git clone -- "$PTR_REPO_URL" "$ROOT"
fi
cd "$ROOT"
if ! command -v docker >/dev/null; then
  . /etc/os-release
  [[ "$ID" == ubuntu || "$ID" == debian ]] || { echo 'Automatic Docker install supports Debian/Ubuntu only'; exit 1; }
  apt-get update
  apt-get install -y ca-certificates curl openssl
  installer="$(mktemp)"
  curl -fsSL https://get.docker.com -o "$installer"
  sh "$installer"
  rm -f -- "$installer"
fi
docker compose version
if [[ ! -f .env ]]; then
  umask 077
  secret="$(openssl rand -base64 32 | tr '+/' '-_')"
  printf 'PTR_SECRET=%s\nPTR_DATA_DIR=./data\nPTR_BIND=127.0.0.1\nPTR_PORT=3000\nPTR_SECURE_COOKIE=0\nPTR_TAG=local\n' "$secret" > .env
fi
mkdir -p data backups
chown 10001:10001 data
chmod 700 data backups
docker compose build
docker compose run --rm --no-deps backend python -m backend.cli migrate
if ! docker compose run --rm --no-deps backend python -c "from backend.store import rows; assert rows(\"SELECT 1 FROM settings WHERE key='admin_password'\")" >/dev/null 2>&1; then
  docker compose run --rm --no-deps backend python -m backend.cli init-admin </dev/tty
fi
docker compose up -d --wait --wait-timeout 180
bash scripts/status.sh
printf '\nPayment Test Runner installed\nMode            LIVE\nWeb URL: http://127.0.0.1:3000\nRemote access: SSH tunnel or HTTPS reverse proxy (see README.md).\n'
