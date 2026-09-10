#!/bin/bash
# Uninstall Corral. Removes everything install.sh and the app create:
#   - the menu bar LaunchAgent (~/Library/LaunchAgents/com.corral.menubar.plist)
#   - LaunchAgents for registered agents (com.corral.agent.*.plist)
#   - the `corral` CLI symlink, if it points into the install directory
#   - the install directory itself (default ~/.corral; override with CORRAL_DIR)
#   - ~/.config/corral (config and registered agent folders); pass --keep-config to keep it
#
# Run from anywhere:
#   ~/.corral/uninstall.sh
#   curl -fsSL https://raw.githubusercontent.com/cultron/corral/main/uninstall.sh | bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "${CORRAL_DIR:-}" ]; then
    DEST="${CORRAL_DIR}"
elif [ -f "${SCRIPT_DIR}/install.sh" ]; then
    DEST="${SCRIPT_DIR}"
else
    DEST="${HOME}/.corral"
fi
CONFIG_DIR="${HOME}/.config/corral"
PLIST_LABEL="${CORRAL_LABEL:-com.corral.menubar}"
LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"
KEEP_CONFIG=no
[ "${1:-}" = "--keep-config" ] && KEEP_CONFIG=yes

echo "Uninstalling Corral from ${DEST}"

# Stop the running app, if any.
pkill -f "${DEST}/venv/bin/python3 -m corral" 2>/dev/null || true

# Menu bar LaunchAgent and any registered agent plists.
for plist in "${LAUNCH_AGENTS}/${PLIST_LABEL}.plist" "${LAUNCH_AGENTS}"/com.corral.agent.*.plist; do
    [ -e "${plist}" ] || continue
    launchctl unload "${plist}" 2>/dev/null || true
    rm -f "${plist}"
    echo "Removed LaunchAgent $(basename "${plist}")"
done

# CLI symlink: only remove links that point into this install.
for d in "${CORRAL_BIN_DIR:-}" "$HOME/bin" "$HOME/.local/bin" /usr/local/bin /opt/homebrew/bin; do
    link="${d:+$d/corral}"
    [ -n "${link}" ] && [ -L "${link}" ] || continue
    case "$(readlink "${link}")" in
        "${DEST}"/*) rm -f "${link}"; echo "Removed CLI link ${link}" ;;
    esac
done

if [ -d "${DEST}" ]; then
    rm -rf "${DEST}"
    echo "Removed ${DEST}"
fi

if [ "${KEEP_CONFIG}" = "yes" ]; then
    echo "Kept ${CONFIG_DIR}"
elif [ -d "${CONFIG_DIR}" ]; then
    rm -rf "${CONFIG_DIR}"
    echo "Removed ${CONFIG_DIR}"
fi

echo "Done."
