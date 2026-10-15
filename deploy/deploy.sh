#!/usr/bin/env bash
# Deploy one version of Nock on the server (docs/hosting.md, section 10).
#
# Usage: deploy.sh <tag>        for example: deploy.sh v1.0.0
#
# Run on the server: by hand over SSH from your computer, or by the optional
# Deploy workflow. Everything happens here, with no image registry:
#   1. fetch the tagged source from GitHub (read-only deploy key),
#   2. update these deploy files from that tag,
#   3. build the image on the server (an Arm machine: no emulation),
#   4. back up the database,
#   5. restart with the new image and check that the app answers; when it does
#      not, start the previous version again and fail.
# Deploying a version whose image is already built (a rollback) skips 1 to 3.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR=/srv/nock/src
REPO_URL="${NOCK_REPO_URL:-git@github.com:Zyniel/nock.git}"
REPO_KEY="${HOME}/.ssh/nock_repo"  # created by setup-server.sh
# Files of deploy/ that come from the tagged version. deploy.sh replaces itself
# by a rename, which is safe while it runs.
DEPLOY_FILES="compose.yaml Caddyfile deploy.sh backup.sh restore-test.sh setup-server.sh .env.example backup.env.example"

cd "$DEPLOY_DIR"

if [ "$#" -ne 1 ] || [[ ! "$1" =~ ^v[0-9A-Za-z._-]+$ ]]; then
    echo "usage: deploy.sh <tag>, for example deploy.sh v1.0.0" >&2
    exit 2
fi
new_tag="$1"

if [ ! -f .env ]; then
    echo "missing ${DEPLOY_DIR}/.env: copy .env.example and fill it in" >&2
    exit 1
fi

previous_tag=""
if [ -f tag.env ]; then
    previous_tag="$(sed -n 's/^NOCK_TAG=//p' tag.env)"
fi

compose_with() {
    local tag_file="$1"
    shift
    docker compose --env-file .env --env-file "$tag_file" "$@"
}

app_answers() {
    # GET / from inside the app container: 200 once the app has started.
    compose_with tag.env exec -T nock python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)" \
        >/dev/null 2>&1
}

wait_for_app() {
    for _ in $(seq 1 30); do
        if app_answers; then
            return 0
        fi
        sleep 2
    done
    return 1
}

fetch_source() {
    export GIT_SSH_COMMAND="ssh -i ${REPO_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
    if [ ! -d "${SOURCE_DIR}/.git" ]; then
        git init --quiet "$SOURCE_DIR"
        git -C "$SOURCE_DIR" remote add origin "$REPO_URL"
    fi
    git -C "$SOURCE_DIR" fetch --quiet --force --depth 1 origin \
        "refs/tags/${new_tag}:refs/tags/${new_tag}"
    git -C "$SOURCE_DIR" checkout --quiet --force --detach "$new_tag"
    git -C "$SOURCE_DIR" clean --quiet -fdx
}

update_deploy_files() {
    local name
    for name in $DEPLOY_FILES; do
        if [ -f "${SOURCE_DIR}/deploy/${name}" ]; then
            cp "${SOURCE_DIR}/deploy/${name}" "${name}.new"
            mv "${name}.new" "$name"
        fi
    done
    mkdir -p systemd
    cp "${SOURCE_DIR}"/deploy/systemd/* systemd/
    chmod +x ./*.sh
}

remove_old_images() {
    # Keep the live version and the one before it (for a quick rollback).
    local image
    docker image ls --format '{{.Repository}}:{{.Tag}}' nock \
        | while read -r image; do
            if [ "$image" != "nock:${new_tag}" ] && [ "$image" != "nock:${previous_tag}" ]; then
                docker image rm "$image" >/dev/null || true
            fi
        done
    docker image prune --force >/dev/null
    docker builder prune --force --filter until=720h >/dev/null
}

if docker image inspect "nock:${new_tag}" >/dev/null 2>&1; then
    echo "== Image nock:${new_tag} is already built"
else
    echo "== Fetching ${new_tag}"
    fetch_source
    update_deploy_files
    echo "== Building nock:${new_tag} (a few minutes)"
    docker build --quiet --tag "nock:${new_tag}" "$SOURCE_DIR" >/dev/null
fi

echo "NOCK_TAG=${new_tag}" >tag.env.new
compose_with tag.env.new pull --quiet caddy

echo "== Backing up the database"
sudo ./backup.sh

echo "== Starting ${new_tag} (was: ${previous_tag:-none})"
mv tag.env.new tag.env
compose_with tag.env up -d --remove-orphans

echo "== Checking that the app answers"
if wait_for_app; then
    echo "== ${new_tag} is live"
    remove_old_images
    exit 0
fi

echo "!! ${new_tag} does not answer; recent logs:" >&2
compose_with tag.env logs --tail 40 nock >&2 || true
if [ -n "$previous_tag" ]; then
    echo "!! Going back to ${previous_tag}" >&2
    echo "NOCK_TAG=${previous_tag}" >tag.env
    compose_with tag.env up -d --remove-orphans
    if wait_for_app; then
        echo "!! ${previous_tag} is live again" >&2
    else
        echo "!! ${previous_tag} does not answer either: the site is down" >&2
    fi
fi
exit 1
