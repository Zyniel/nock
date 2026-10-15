#!/usr/bin/env bash
# Restore test (docs/hosting.md, section 6). Run as root: monthly by the
# nock-restore-test timer, or by hand after any change to the backups.
#
# Takes the newest off-site backup (or the newest local one when there is no
# backup.env), checks it with PRAGMA integrity_check, starts the current app
# image on it in a throwaway container with no network, checks that the app
# answers, then deletes everything it made. The live app is not touched.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_DIR=/srv/nock/backups
WORK_ROOT=/srv/nock/restore-test
APP_UID=10001
CONTAINER=nock-restore-test

if [ "$(id -u)" -ne 0 ]; then
    echo "run as root (sudo)" >&2
    exit 1
fi

tag="$(sed -n 's/^NOCK_TAG=//p' "${DEPLOY_DIR}/tag.env" 2>/dev/null || true)"
if [ -z "$tag" ]; then
    echo "no tag.env: deploy a version first" >&2
    exit 1
fi

work="$(mktemp -d "${WORK_ROOT}.XXXXXX")"
# shellcheck disable=SC2329  # called by the EXIT trap
cleanup() {
    docker rm --force "$CONTAINER" >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

if [ -f "${DEPLOY_DIR}/backup.env" ]; then
    set -a
    # shellcheck source=/dev/null
    . "${DEPLOY_DIR}/backup.env"
    set +a
    newest="$(rclone -q lsf --files-only nockbackup: | sort | tail -n 1)"
    if [ -z "$newest" ]; then
        echo "no off-site backup found" >&2
        exit 1
    fi
    rclone -q copy "nockbackup:${newest}" "$work"
    echo "testing off-site backup ${newest}"
else
    newest="$(find "$LOCAL_DIR" -maxdepth 1 -name 'nock-*.sqlite3.gz' -printf '%f\n' | sort | tail -n 1)"
    if [ -z "$newest" ]; then
        echo "no local backup found" >&2
        exit 1
    fi
    cp "${LOCAL_DIR}/${newest}" "$work/"
    echo "WARNING: no backup.env, testing local backup ${newest}" >&2
fi

gunzip "${work}/${newest}"
database="${work}/${newest%.gz}"
mv "$database" "${work}/nock.sqlite3"
chown -R "$APP_UID:$APP_UID" "$work"

check="$(sqlite3 "${work}/nock.sqlite3" "PRAGMA integrity_check")"
if [ "$check" != "ok" ]; then
    echo "integrity check failed: ${check}" >&2
    exit 1
fi
tables="$(sqlite3 "${work}/nock.sqlite3" "SELECT count(*) FROM sqlite_master WHERE type = 'table'")"
echo "integrity ok, ${tables} tables"

docker run --detach --name "$CONTAINER" --network none \
    --volume "${work}:/data" \
    "nock:${tag}" >/dev/null

for _ in $(seq 1 30); do
    if docker exec "$CONTAINER" python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)" \
        >/dev/null 2>&1; then
        echo "restore test passed: ${tag} starts and answers on the restored database"
        exit 0
    fi
    sleep 2
done

echo "restore test failed: the app did not answer; its logs:" >&2
docker logs --tail 40 "$CONTAINER" >&2 || true
exit 1
