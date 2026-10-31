#!/bin/sh
# Pull, restart, and put it back if the clock does not come up.
#
# Started detached by the web interface, because restarting the service kills
# the process that asked for the update. It is copied out of the checkout
# before it runs: /bin/sh reads a script as it executes, and the checkout is
# about to change underneath it.
#
#   self-update.sh REPOSITORY OWNER SERVICE PORT
#
# Git runs as the checkout's owner rather than root, which is both what
# satisfies git's ownership check and what keeps root-owned objects out of a
# repository the owner still has to use.

set -u

REPOSITORY=$1
OWNER=$2
SERVICE=$3
PORT=$4

log() { echo "self-update: $*"; logger -t wordclock-update "$*" 2>/dev/null || true; }

as_owner() {
    if [ -n "$OWNER" ] && [ "$OWNER" != "$(id -un)" ]; then
        sudo -n -u "$OWNER" "$@"
    else
        "$@"
    fi
}

healthy() {
    python3 - "$PORT" <<'EOF' 2>/dev/null
import sys, urllib.request
urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/api/state", timeout=3).read(1)
EOF
}

BEFORE=$(as_owner git -C "$REPOSITORY" rev-parse HEAD) || exit 1
log "updating from $BEFORE"

if ! as_owner git -C "$REPOSITORY" merge --ff-only "@{u}"; then
    log "could not fast-forward; nothing changed"
    exit 1
fi

AFTER=$(as_owner git -C "$REPOSITORY" rev-parse HEAD)
if [ "$AFTER" = "$BEFORE" ]; then
    log "already up to date"
    exit 0
fi
log "updated to $AFTER, restarting"

systemctl restart "$SERVICE"

# Give it a generous window: a Pi Zero takes a while to import Pillow, and
# rolling back a clock that was merely slow would be its own bug.
i=0
while [ "$i" -lt 45 ]; do
    if healthy; then
        log "healthy on $AFTER"
        exit 0
    fi
    i=$((i + 1))
    sleep 2
done

log "no answer after 90s, rolling back to $BEFORE"
as_owner git -C "$REPOSITORY" reset --hard "$BEFORE"
systemctl restart "$SERVICE"
log "rolled back"
exit 1
