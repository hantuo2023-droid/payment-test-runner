#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
require_docker
mkdir -p backups
chmod 700 backups
archive="$ROOT/backups/ptr-$(date -u +%Y%m%dT%H%M%SZ)-$$.tar.gz"
# Stop worker before copying DB, WAL, evidence and encryption configuration as a unit.
dc stop backend
trap 'dc up -d backend >/dev/null' EXIT
umask 077
dc run --rm --no-deps --user root --entrypoint tar -v "$ROOT/backups:/backups" backend -czf "/backups/$(basename "$archive")" -C / data
tar -czf "$archive.env.tar.gz" .env
printf '%s\n' "$archive"
