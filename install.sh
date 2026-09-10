#!/bin/bash
# Install Corral: venv, dependencies, optional start-at-login.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
PLIST_LABEL="${CORRAL_LABEL:-com.corral.menubar}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

echo "Setting up Corral..."

# Pick a Python interpreter. pyobjc only publishes prebuilt wheels for
# Python 3.10+ (and only pyobjc 11.x for 3.9), so prefer a modern
# interpreter from Homebrew/python.org over the Xcode-bundled 3.9.
# Override with CORRAL_PYTHON=/path/to/python3.
py_minor() { "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null; }

pick_python() {
    if [ -n "${CORRAL_PYTHON:-}" ]; then
        echo "${CORRAL_PYTHON}"
        return
    fi
    local name dir cand
    for name in python3.14 python3.13 python3.12 python3.11 python3.10; do
        for dir in "" /opt/homebrew/bin /usr/local/bin \
                   "/Library/Frameworks/Python.framework/Versions/${name#python}/bin"; do
            if [ -z "${dir}" ]; then
                cand="$(command -v "${name}" 2>/dev/null || true)"
            else
                cand="${dir}/${name}"
            fi
            if [ -n "${cand}" ] && [ -x "${cand}" ] && "${cand}" -c 'import venv' >/dev/null 2>&1; then
                echo "${cand}"
                return
            fi
        done
    done
    command -v python3 || true
}

PYTHON="$(pick_python)"
if [ -z "${PYTHON}" ]; then
    echo "corral: python3 not found. Install Python 3.10+ (e.g. 'brew install python')." >&2
    exit 1
fi
PY_VER="$(py_minor "${PYTHON}")"
case "${PY_VER}" in
    3.[0-8]|2.*|"")
        echo "corral: Python ${PY_VER:-?} at ${PYTHON} is too old. Install Python 3.10+ (e.g. 'brew install python')." >&2
        exit 1 ;;
    3.9)
        echo "Using Python 3.9 at ${PYTHON} (pyobjc 11.x). Python 3.10+ is recommended; run 'brew install python' and re-run this installer to upgrade." ;;
    *)
        echo "Using Python ${PY_VER} at ${PYTHON}" ;;
esac

# Recreate the venv if it was built with a different Python (e.g. an
# earlier install on the Xcode 3.9 that later gained a Homebrew Python).
if [ -d "${VENV_DIR}" ]; then
    VENV_VER="$(py_minor "${VENV_DIR}/bin/python3" || true)"
    if [ "${VENV_VER}" != "${PY_VER}" ]; then
        echo "Recreating virtual environment (Python ${VENV_VER:-?} -> ${PY_VER})..."
        rm -rf "${VENV_DIR}"
    fi
fi

if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment..."
    "${PYTHON}" -m venv "${VENV_DIR}"
fi

echo "Installing dependencies..."
"${VENV_DIR}/bin/python3" -m pip install -q --upgrade pip
# Never compile pyobjc from source: it is slow and breaks with new Xcode
# releases. Require wheels and fail with a clear message instead.
if ! "${VENV_DIR}/bin/python3" -m pip install -q \
        --only-binary pyobjc-core,pyobjc-framework-Cocoa \
        -r "${SCRIPT_DIR}/requirements.txt"; then
    echo "" >&2
    echo "corral: could not install dependencies for Python ${PY_VER}." >&2
    echo "        pyobjc has no prebuilt wheel for this interpreter. Install a newer" >&2
    echo "        Python (e.g. 'brew install python') and re-run, or point CORRAL_PYTHON" >&2
    echo "        at one, e.g. CORRAL_PYTHON=/opt/homebrew/bin/python3 ./install.sh" >&2
    exit 1
fi

echo "Writing default config if missing..."
"${VENV_DIR}/bin/python3" -c "from corral.config import write_default_config, CONFIG_PATH; created = write_default_config(); print(('Created ' if created else 'Kept existing ') + CONFIG_PATH)"

# Earlier versions built a Corral.app wrapper here. Launching through it
# (open -W + a shell script that execs Python) left the menu bar item
# unhosted on macOS 26, so the login item now runs Python directly.
rm -rf "${SCRIPT_DIR}/Corral.app"
mkdir -p "${SCRIPT_DIR}/logs"

echo ""
echo "Done. Run directly with:"
echo "  ${VENV_DIR}/bin/python3 -m corral"
echo ""

# Put the corral CLI on the PATH
BIN_TARGET="${CORRAL_BIN_DIR:-}"
if [ -z "${BIN_TARGET}" ]; then
    for d in "$HOME/bin" "$HOME/.local/bin" "/usr/local/bin" "/opt/homebrew/bin"; do
        case ":$PATH:" in *":$d:"*) [ -w "$d" ] && BIN_TARGET="$d" && break ;; esac
    done
fi
if [ -n "${BIN_TARGET}" ] && [ "${BIN_TARGET}" != "skip" ]; then
    ln -sf "${SCRIPT_DIR}/bin/corral" "${BIN_TARGET}/corral"
    echo "Linked corral CLI: ${BIN_TARGET}/corral"
else
    echo "Add the CLI to your PATH with:"
    echo "  ln -s ${SCRIPT_DIR}/bin/corral /usr/local/bin/corral"
fi
echo ""

INSTALL_AGENT="${CORRAL_AUTOSTART:-ask}"
if [ "${INSTALL_AGENT}" = "ask" ]; then
    read -p "Start Corral at login? [y/N] " -n 1 -r
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
        <string>${VENV_DIR}/bin/python3</string>
        <string>-m</string>
        <string>corral</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
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
    # Older login items launched via `open`, so unloading them left the
    # Python process behind. Stop any running copy before starting the new one.
    pkill -f -- ' -m corral$' 2>/dev/null || true
    launchctl load "${PLIST_PATH}"
    echo "Corral will start at login (login item: ${PLIST_PATH})"
fi
