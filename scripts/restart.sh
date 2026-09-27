#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
dc restart
dc up -d --wait --wait-timeout 180
bash scripts/status.sh
