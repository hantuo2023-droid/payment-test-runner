#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
require_docker
exec 9>"$ROOT/.git/ptr-update.lock"
flock -n 9 || { echo 'Another update is already running'; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo 'Working tree must be clean'; exit 1; }
old="$(git rev-parse HEAD)"
branch="$(git symbolic-ref --short HEAD)"
dc stop frontend
bash scripts/backup.sh || { dc up -d frontend; exit 1; }
backup="$(find "$ROOT/backups" -maxdepth 1 -name 'ptr-*.tar.gz' ! -name '*.env.tar.gz' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
rollback() {
  trap - ERR
  echo 'UPDATE FAILED. Restoring previous code, database and images.' >&2
  dc stop backend frontend || true
  git checkout --detach "$old"
  tar -xzf "$backup.env.tar.gz" -C "$ROOT"
  dc run --rm --no-deps --user root --entrypoint python -v "$ROOT/backups:/backup:ro" backend -c 'import pathlib,shutil,tarfile,sys,os; root=pathlib.Path("/data"); [shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink() for p in root.iterdir()]; tarfile.open(sys.argv[1]).extractall("/",filter="data"); [os.chown(p,10001,10001) for p in [root,*root.rglob("*")]]' "/backup/$(basename "$backup")"
  dc up -d --wait --wait-timeout 180
  bash scripts/status.sh
  echo "Rollback complete at $old. Investigate before switching back to $branch." >&2
  exit 1
}
trap rollback ERR
git pull --ff-only
new="$(git rev-parse --short HEAD)"
sed -i "s/^PTR_TAG=.*/PTR_TAG=$new/" .env
dc build
dc stop backend frontend
dc run --rm --no-deps backend python -m backend.cli migrate
dc up -d --wait --wait-timeout 180
bash scripts/status.sh
trap - ERR
echo "Updated successfully to $new"
