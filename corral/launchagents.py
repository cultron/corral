"""Discovery and control of user LaunchAgents via launchctl."""

import fnmatch
import glob
import os
import plistlib
import subprocess

LAUNCHAGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")

WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Reverse-DNS first components stripped when building display names.
_TLD_PREFIXES = {"com", "org", "net", "io", "ai", "dev", "app", "us", "co", "me", "homebrew"}


def get_agents(patterns):
    """Return parsed plists for LaunchAgents matching the label patterns.

    With no patterns, every non-Apple plist in ~/Library/LaunchAgents is
    included.
    """
    agents = []
    for plist_path in sorted(glob.glob(os.path.join(LAUNCHAGENTS_DIR, "*.plist"))):
        name = os.path.basename(plist_path)[: -len(".plist")]
        if patterns:
            if not any(fnmatch.fnmatch(name, p) for p in patterns):
                continue
        elif name.startswith("com.apple."):
            continue
        try:
            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)
        except Exception:
            continue
        agents.append({
            "label": plist.get("Label", name),
            "plist_path": plist_path,
            "program_arguments": plist.get("ProgramArguments", []),
            "stdout_log": plist.get("StandardOutPath", ""),
            "stderr_log": plist.get("StandardErrorPath", ""),
            "schedule": plist.get("StartCalendarInterval"),
            "keep_alive": bool(plist.get("KeepAlive", False)),
            "run_at_load": bool(plist.get("RunAtLoad", False)),
        })
    return agents


def get_status_map():
    """Parse `launchctl list` once into {label: (pid, exit_code)}."""
    statuses = {}
    try:
        result = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) == 3:
                statuses[parts[2]] = (parts[0].strip(), parts[1].strip())
    except Exception:
        pass
    return statuses


def agent_status(label, status_map):
    """Return (pid, exit_code, is_loaded, is_running, has_error)."""
    if label not in status_map:
        return None, None, False, False, False
    pid, exit_code = status_map[label]
    is_running = pid not in ("-", "")
    has_error = exit_code not in ("0", "-", "")
    return pid, exit_code, True, is_running, has_error


def start(label, plist_path):
    subprocess.run(["launchctl", "load", plist_path], capture_output=True, timeout=10)
    subprocess.run(["launchctl", "start", label], capture_output=True, timeout=10)


def stop(label, plist_path):
    subprocess.run(["launchctl", "stop", label], capture_output=True, timeout=10)
    subprocess.run(["launchctl", "unload", plist_path], capture_output=True, timeout=10)


def restart(label, plist_path):
    stop(label, plist_path)
    start(label, plist_path)


def friendly_name(label):
    """com.mavric.susie.morning-brief -> Susie / Morning Brief."""
    parts = label.split(".")
    if len(parts) > 2 and parts[0] in _TLD_PREFIXES:
        parts = parts[2:]
    formatted = [p.replace("-", " ").replace("_", " ").title() for p in parts]
    return " / ".join(formatted)


def group_key(label):
    """Grouping key for the menu: the org-stripped first component when
    the label has sub-parts, else None (standalone)."""
    parts = label.split(".")
    if len(parts) > 2 and parts[0] in _TLD_PREFIXES:
        parts = parts[2:]
    return parts[0] if len(parts) > 1 else None


def format_schedule(schedule):
    if not schedule:
        return "No schedule"
    entries = schedule if isinstance(schedule, list) else [schedule]
    return " | ".join(_format_entry(e) for e in entries)


def _format_entry(entry):
    if not isinstance(entry, dict):
        return "?"
    hour = entry.get("Hour")
    minute = entry.get("Minute", 0)
    weekday = entry.get("Weekday")
    time_str = f"{hour}:{minute:02d}" if hour is not None else "?"
    if weekday is not None:
        return f"{WEEKDAYS[weekday]} {time_str}"
    return f"Daily {time_str}"


def tail_file(path, lines=200):
    """Return the last N lines of a file, or None if unreadable."""
    if not path or not os.path.exists(path):
        return None
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), path],
            capture_output=True, text=True, timeout=5, errors="replace"
        )
        return result.stdout
    except Exception:
        return None
