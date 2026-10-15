#!/usr/bin/env bash
# One-time setup of a new Ubuntu 24.04 server for Nock (docs/oracle-setup.md,
# step 8). Safe to run again: each step checks what is already done.
#
# Usage, from the folder holding this script:
#   sudo bash setup-server.sh /dev/sdb     # with the data block volume (Oracle)
#   sudo bash setup-server.sh              # no separate volume: data on the boot disk
#
# It installs Docker (with BuildKit), git, SQLite and rclone, opens ports 80 and
# 443 in the server's firewall, keeps logs 14 days, mounts the data volume at
# /srv/nock, creates the folders, copies this deploy folder to /srv/nock/deploy,
# turns on the nightly backup and monthly restore-test timers, and creates the
# key the server uses to read the repository (printed at the end).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT=/srv/nock
APP_UID=10001  # the user of the app image (Dockerfile)
ADMIN_USER="${SUDO_USER:-ubuntu}"

if [ "$(id -u)" -ne 0 ]; then
    echo "run with sudo: sudo bash setup-server.sh [/dev/sdX]" >&2
    exit 1
fi
device="${1:-}"

step() {
    echo
    echo "== $*"
}

step "System updates and packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y upgrade
apt-get -y install docker.io docker-compose-v2 docker-buildx git sqlite3 \
    rclone curl unattended-upgrades iptables-persistent
systemctl enable --now docker
usermod -aG docker "$ADMIN_USER"

step "Firewall: allow HTTP (80) and HTTPS (443)"
# Oracle's Ubuntu images reject every port but 22 in their iptables rules.
# Add the two rules live and in the saved file, next to the SSH rule. (The
# saved file is edited rather than re-saved, so Docker's own rules stay out.)
rules_file=/etc/iptables/rules.v4
for port in 80 443; do
    rule="-p tcp -m state --state NEW -m tcp --dport ${port} -j ACCEPT"
    # shellcheck disable=SC2086
    if ! iptables -C INPUT $rule 2>/dev/null; then
        # shellcheck disable=SC2086
        iptables -I INPUT $rule
    fi
    if [ -f "$rules_file" ] && ! grep -q -- "--dport ${port} -j ACCEPT" "$rules_file"; then
        sed -i "/--dport 22 -j ACCEPT/a -A INPUT ${rule}" "$rules_file"
    fi
done

step "Logs: keep 14 days (docs/hosting.md, section 9)"
mkdir -p /etc/systemd/journald.conf.d
cat >/etc/systemd/journald.conf.d/nock.conf <<'EOF'
[Journal]
MaxRetentionSec=14day
EOF
systemctl restart systemd-journald

step "Data volume"
if [ -n "$device" ]; then
    if [ ! -b "$device" ]; then
        echo "${device} is not a disk; check the name with: lsblk" >&2
        exit 1
    fi
    if ! blkid "$device" >/dev/null 2>&1; then
        echo "${device} has no file system yet. Formatting ERASES it."
        read -r -p "Type yes to format ${device}: " answer
        if [ "$answer" != "yes" ]; then
            echo "stopped, nothing formatted" >&2
            exit 1
        fi
        mkfs.ext4 -L nock-data "$device"
    fi
    uuid="$(blkid -s UUID -o value "$device")"
    mkdir -p "$ROOT"
    if ! grep -q "$uuid" /etc/fstab; then
        echo "UUID=${uuid} ${ROOT} ext4 defaults,nofail,_netdev 0 2" >>/etc/fstab
    fi
    systemctl daemon-reload
    mountpoint -q "$ROOT" || mount "$ROOT"
    echo "${device} mounted at ${ROOT}"
else
    echo "no device given: data stays on the boot disk under ${ROOT}"
fi

step "Folders"
mkdir -p "$ROOT"/{deploy,src,data,grids,backups,caddy/data,caddy/config}
chown "$APP_UID:$APP_UID" "$ROOT/data" "$ROOT/backups"
chmod 700 "$ROOT/data" "$ROOT/backups"
chown "$ADMIN_USER:$ADMIN_USER" "$ROOT/deploy" "$ROOT/src" "$ROOT/grids"

step "Deploy files"
if [ "$SCRIPT_DIR" != "$ROOT/deploy" ]; then
    cp -r "$SCRIPT_DIR"/. "$ROOT/deploy/"
    chown -R "$ADMIN_USER:$ADMIN_USER" "$ROOT/deploy"
fi
chmod +x "$ROOT"/deploy/*.sh

step "Backup and restore-test timers"
cp "$ROOT"/deploy/systemd/*.service "$ROOT"/deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now nock-backup.timer nock-restore-test.timer

step "Key to read the repository (deploy.sh fetches each version with it)"
admin_home="$(getent passwd "$ADMIN_USER" | cut -d: -f6)"
repo_key="${admin_home}/.ssh/nock_repo"
if [ ! -f "$repo_key" ]; then
    sudo -u "$ADMIN_USER" mkdir -p "${admin_home}/.ssh"
    sudo -u "$ADMIN_USER" ssh-keygen -q -t ed25519 -N "" -C "nock server (read-only)" -f "$repo_key"
fi

echo
echo "Done. Next (docs/oracle-setup.md):"
echo "- add this key on GitHub as a read-only deploy key (step 11):"
echo
cat "${repo_key}.pub"
echo
echo "- create ${ROOT}/deploy/.env from .env.example (step 9),"
echo "  and ${ROOT}/deploy/backup.env from backup.env.example (step 10);"
echo "- log out and in again so that ${ADMIN_USER} can use docker."
