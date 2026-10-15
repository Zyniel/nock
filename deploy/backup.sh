#!/usr/bin/env bash
# Back up the Nock database (docs/hosting.md, section 6). Run as root: nightly by
# the nock-backup timer, and by deploy.sh before each deployment.
#
# 1. An online, consistent copy with SQLite's VACUUM INTO (never a plain file
#    copy: the database is in WAL mode), checked with PRAGMA integrity_check.
# 2. Compressed, kept in /srv/nock/backups (the newest KEEP_LOCAL copies).
# 3. When backup.env exists: uploaded, encrypted by rclone's crypt remote, to the
#    Object Storage bucket, and copies older than KEEP_DAYS deleted there. Then,
#    when BACKUP_PING_URL is set, a ping tells the monitoring service it worked.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
DATABASE=/srv/nock/data/nock.sqlite3
LOCAL_DIR=/srv/nock/backups
APP_UID=10001  # the user of the app image (Dockerfile)
KEEP_LOCAL=3
KEEP_DAYS=14  # spec 038: deleted data leaves every copy within 14 days

if [ "$(id -u)" -ne 0 ]; then
    echo "run as root (sudo)" >&2
    exit 1
fi

if [ ! -f "$DATABASE" ]; then
    echo "no database yet at ${DATABASE}: nothing to back up"
    exit 0
fi

as_app() {
    # SQLite runs as the app's user, so any -wal or -shm file it creates
    # stays usable by the app.
    setpriv --reuid="$APP_UID" --regid="$APP_UID" --clear-groups "$@"
}

mkdir -p "$LOCAL_DIR"
chown "$APP_UID:$APP_UID" "$LOCAL_DIR"
chmod 700 "$LOCAL_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
copy="${LOCAL_DIR}/nock-${stamp}.sqlite3"

as_app sqlite3 "$DATABASE" "VACUUM INTO '${copy}'"
check="$(as_app sqlite3 "$copy" "PRAGMA integrity_check")"
if [ "$check" != "ok" ]; then
    echo "integrity check failed on ${copy}: ${check}" >&2
    exit 1
fi
gzip "$copy"
echo "local copy: ${copy}.gz"

# Keep the newest KEEP_LOCAL local copies.
find "$LOCAL_DIR" -maxdepth 1 -name 'nock-*.sqlite3.gz' -printf '%f\n' \
    | sort -r \
    | tail -n +"$((KEEP_LOCAL + 1))" \
    | while read -r old; do rm -f "${LOCAL_DIR}/${old}"; done

if [ ! -f "${DEPLOY_DIR}/backup.env" ]; then
    echo "WARNING: no ${DEPLOY_DIR}/backup.env, so no off-site copy" >&2
    exit 0
fi

set -a
# shellcheck source=/dev/null
. "${DEPLOY_DIR}/backup.env"
set +a

rclone -q copy "${copy}.gz" nockbackup:
rclone -q delete --min-age "${KEEP_DAYS}d" nockbackup:
echo "off-site copy uploaded; copies older than ${KEEP_DAYS} days deleted"

if [ -n "${BACKUP_PING_URL:-}" ]; then
    curl -fsS -m 10 --retry 3 "$BACKUP_PING_URL" >/dev/null || true
fi
