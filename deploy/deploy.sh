#!/usr/bin/env bash
# Deploy one version of the Nock image on the server (docs/hosting.md, section 10).
#
# Usage: deploy.sh <tag>        for example: deploy.sh v1.0.0
#
# Run by the deploy workflow over SSH, after it logged Docker in to ghcr.io; it
# can also be run by hand on the server. Steps: pull the new image, back up the
# database, restart with the new image, check that the app answers. When the
# check fails, the previous version is started again and the script fails.
set -euo pipefail

cd "$(dirname "$0")"

if [ "$#" -ne 1 ] || [[ ! "$1" =~ ^v[0-9A-Za-z._-]+$ ]]; then
    echo "usage: deploy.sh <tag>, for example deploy.sh v1.0.0" >&2
    exit 2
fi
new_tag="$1"

if [ ! -f .env ]; then
    echo "missing $(pwd)/.env: copy .env.example and fill it in" >&2
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

echo "NOCK_TAG=${new_tag}" >tag.env.new

echo "== Pulling ${new_tag}"
compose_with tag.env.new pull

echo "== Backing up the database"
sudo ./backup.sh

echo "== Starting ${new_tag} (was: ${previous_tag:-none})"
mv tag.env.new tag.env
compose_with tag.env up -d --remove-orphans

echo "== Checking that the app answers"
if wait_for_app; then
    echo "== ${new_tag} is live"
    docker image prune --force >/dev/null
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
