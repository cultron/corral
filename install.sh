#!/bin/bash
# Install Agent Monitor: venv, dependencies, .app bundle, optional LaunchAgent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
APP_DIR="${SCRIPT_DIR}/AgentMonitor.app"
PLIST_LABEL="${AGENT_MONITOR_LABEL:-com.agentmonitor.menubar}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

echo "Setting up Agent Monitor..."

if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
fi

echo "Installing dependencies..."
"${VENV_DIR}/bin/pip" install -q -r "${SCRIPT_DIR}/requirements.txt"

echo "Writing default config if missing..."
"${VENV_DIR}/bin/python3" -c "from agentmonitor.config import write_default_config, CONFIG_PATH; created = write_default_config(); print(('Created ' if created else 'Kept existing ') + CONFIG_PATH)"

echo "Building app bundle..."
mkdir -p "${APP_DIR}/Contents/MacOS" "${SCRIPT_DIR}/logs"
cat > "${APP_DIR}/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>AgentMonitor</string>
    <key>CFBundleIdentifier</key>
    <string>${PLIST_LABEL}</string>
    <key>CFBundleVersion</key>
    <string>0.2.0</string>
    <key>CFBundleExecutable</key>
    <string>launch</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF
cat > "${APP_DIR}/Contents/MacOS/launch" << EOF
#!/bin/bash
cd "${SCRIPT_DIR}"
exec "${VENV_DIR}/bin/python3" -m agentmonitor
EOF
chmod +x "${APP_DIR}/Contents/MacOS/launch"

echo ""
echo "Done. Run directly with:"
echo "  ${VENV_DIR}/bin/python3 -m agentmonitor"
echo ""

INSTALL_AGENT="${AGENT_MONITOR_AUTOSTART:-ask}"
if [ "${INSTALL_AGENT}" = "ask" ]; then
    read -p "Create a LaunchAgent so it starts at login? [y/N] " -n 1 -r
    echo ""
    [[ $REPLY =~ ^[Yy]$ ]] && INSTALL_AGENT="yes" || INSTALL_AGENT="no"
fi

if [ "${INSTALL_AGENT}" = "yes" ]; then
    cat > "${PLIST_PATH}" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>-W</string>
        <string>${APP_DIR}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/logs/stderr.log</string>
</dict>
</plist>
EOF
    launchctl unload "${PLIST_PATH}" 2>/dev/null || true
    launchctl load "${PLIST_PATH}"
    echo "LaunchAgent installed and loaded: ${PLIST_PATH}"
fi
