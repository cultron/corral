"""Opening commands in the user's terminal (iTerm2 or Terminal.app)."""

import os
import shlex
import subprocess


def pick_terminal(preference="auto"):
    if preference in ("iterm", "iterm2"):
        return "iterm"
    if preference == "terminal":
        return "terminal"
    if os.path.exists("/Applications/iTerm.app"):
        return "iterm"
    return "terminal"


def resume_command(cwd, session_id):
    parts = []
    if cwd and os.path.isdir(cwd):
        parts.append(f"cd {shlex.quote(cwd)}")
    parts.append(f"claude --resume {shlex.quote(session_id)}")
    return " && ".join(parts)


def open_in_terminal(command, preference="auto"):
    """Open a new terminal window running the command."""
    app = pick_terminal(preference)
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    if app == "iterm":
        script = f'''
        tell application "iTerm"
            activate
            set newWindow to (create window with default profile)
            tell current session of newWindow
                write text "{escaped}"
            end tell
        end tell
        '''
    else:
        script = f'''
        tell application "Terminal"
            activate
            do script "{escaped}"
        end tell
        '''
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=15
    )
    return result.returncode == 0, result.stderr.strip()


def copy_to_clipboard(text):
    subprocess.run(["pbcopy"], input=text.encode(), timeout=5)
