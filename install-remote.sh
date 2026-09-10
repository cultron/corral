#!/bin/bash
# Corral one-line installer:
#   curl -fsSL https://raw.githubusercontent.com/cultron/corral/main/install-remote.sh | bash
#
# Clones (or updates) Corral into $CORRAL_DIR (default ~/.corral) and
# runs the standard installer. When no terminal is attached, the
# LaunchAgent is installed automatically; set CORRAL_AUTOSTART=no to
# skip it.
set -euo pipefail

REPO_URL="https://github.com/cultron/corral"
DEST="${CORRAL_DIR:-$HOME/.corral}"

if ! command -v python3 >/dev/null; then
    echo "corral: python3 is required. Install the Xcode Command Line Tools or Python 3.9+." >&2
    exit 1
fi

if [ -d "${DEST}/.git" ]; then
    echo "Updating existing Corral install at ${DEST}"
    git -C "${DEST}" pull --ff-only
elif command -v git >/dev/null; then
    echo "Cloning Corral into ${DEST}"
    git clone --depth 1 "${REPO_URL}.git" "${DEST}"
else
    echo "git not found; downloading Corral into ${DEST}"
    mkdir -p "${DEST}"
    curl -fsSL "${REPO_URL}/archive/refs/heads/main.tar.gz" | tar -xz --strip-components=1 -C "${DEST}"
fi

cd "${DEST}"
if [ -t 1 ] && [ -e /dev/tty ]; then
    ./install.sh < /dev/tty
else
    CORRAL_AUTOSTART="${CORRAL_AUTOSTART:-yes}" ./install.sh
fi
