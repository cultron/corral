"""The registered agents folder.

Every Corral-managed agent lives in ~/.config/corral/agents/<name>/ as
an agent.json plus a prompt.md. `sync` materializes each one as a
launchd plist labeled com.corral.agent.<name> that invokes
`corral run <name>`, and removes plists whose agent folder is gone.
"""

import json
import os
import plistlib
import re
import subprocess
import sys

AGENTS_DIR = os.path.expanduser("~/.config/corral/agents")
LABEL_PREFIX = "com.corral.agent."
LAUNCHAGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# The default command receives the prompt file contents. {prompt} and
# {prompt_file} are substituted at run time by runner.py.
DEFAULT_COMMAND = ["claude", "-p", "{prompt}"]


class RegistryError(Exception):
    pass


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def agent_dir(name):
    return os.path.join(AGENTS_DIR, name)


def plist_path(name):
    return os.path.join(LAUNCHAGENTS_DIR, f"{LABEL_PREFIX}{name}.plist")


def validate_name(name):
    if not _NAME_RE.match(name or ""):
        raise RegistryError(
            f"invalid agent name {name!r}: use lowercase letters, digits, - and _"
        )


def list_registered():
    agents = []
    if not os.path.isdir(AGENTS_DIR):
        return agents
    for name in sorted(os.listdir(AGENTS_DIR)):
        meta = load(name)
        if meta:
            agents.append(meta)
    return agents


def load(name):
    path = os.path.join(agent_dir(name), "agent.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            cfg = json.load(f)
    except Exception as e:
        return {"name": name, "dir": agent_dir(name), "error": str(e)}
    prompt_path = os.path.join(agent_dir(name), "prompt.md")
    return {
        "name": name,
        "dir": agent_dir(name),
        "config": cfg,
        "prompt_path": prompt_path if os.path.isfile(prompt_path) else None,
        "label": LABEL_PREFIX + name,
        "plist_path": plist_path(name),
    }


def add(name, prompt_text=None, command=None, schedule=None,
        interval_seconds=None, keep_alive=False, workdir=None, env=None,
        description="", launchd_extra=None):
    """Create the agent folder. Fails if the agent already exists."""
    validate_name(name)
    d = agent_dir(name)
    if os.path.isdir(d):
        raise RegistryError(f"agent {name!r} already exists at {d}")
    os.makedirs(os.path.join(d, "logs"))
    cfg = {
        "description": description,
        "command": command,          # null means DEFAULT_COMMAND
        "schedule": schedule,        # launchd StartCalendarInterval dict or list
        "interval_seconds": interval_seconds,
        "keep_alive": bool(keep_alive),
        "workdir": workdir,
        "env": env or {},
        # Extra launchd keys merged into the generated plist verbatim,
        # e.g. WatchPaths, ThrottleInterval, or a KeepAlive dict.
        "launchd_extra": launchd_extra or {},
    }
    with open(os.path.join(d, "agent.json"), "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    with open(os.path.join(d, "prompt.md"), "w") as f:
        f.write(prompt_text or "")
    return load(name)


def remove(name, purge=False):
    """Unload and delete the plist. With purge, delete the folder too."""
    validate_name(name)
    pp = plist_path(name)
    if os.path.exists(pp):
        subprocess.run(["launchctl", "unload", pp], capture_output=True, timeout=10)
        os.remove(pp)
    if purge and os.path.isdir(agent_dir(name)):
        import shutil
        shutil.rmtree(agent_dir(name))


def sync(python_exec=None, quiet=False):
    """Write and (re)load a plist per registered agent; drop stale ones."""
    python_exec = python_exec or sys.executable
    say = (lambda *a: None) if quiet else print

    registered = {a["name"]: a for a in list_registered() if "config" in a}

    # Remove plists for agents that no longer exist
    for fname in os.listdir(LAUNCHAGENTS_DIR):
        if not (fname.startswith(LABEL_PREFIX) and fname.endswith(".plist")):
            continue
        name = fname[len(LABEL_PREFIX):-len(".plist")]
        if name not in registered:
            pp = os.path.join(LAUNCHAGENTS_DIR, fname)
            subprocess.run(["launchctl", "unload", pp], capture_output=True, timeout=10)
            os.remove(pp)
            say(f"removed stale {fname}")

    for name, meta in registered.items():
        cfg = meta["config"]
        logs_dir = os.path.join(meta["dir"], "logs")
        os.makedirs(logs_dir, exist_ok=True)
        plist = {
            "Label": meta["label"],
            "ProgramArguments": [python_exec, "-m", "corral", "run", name],
            "WorkingDirectory": _repo_root(),
            "RunAtLoad": bool(cfg.get("keep_alive")),
            "StandardOutPath": os.path.join(logs_dir, "launchd-stdout.log"),
            "StandardErrorPath": os.path.join(logs_dir, "launchd-stderr.log"),
        }
        if cfg.get("keep_alive"):
            plist["KeepAlive"] = True
        if cfg.get("schedule"):
            plist["StartCalendarInterval"] = cfg["schedule"]
        if cfg.get("interval_seconds"):
            plist["StartInterval"] = int(cfg["interval_seconds"])
        if cfg.get("env"):
            plist["EnvironmentVariables"] = {k: str(v) for k, v in cfg["env"].items()}
        plist.update(cfg.get("launchd_extra") or {})

        # Skip reload when nothing changed, so syncing after adding one
        # agent does not bounce every running daemon.
        pp = meta["plist_path"]
        new_bytes = plistlib.dumps(plist)
        try:
            with open(pp, "rb") as f:
                unchanged = f.read() == new_bytes
        except OSError:
            unchanged = False
        if unchanged and _is_loaded(meta["label"]):
            say(f"unchanged {meta['label']}")
            continue

        subprocess.run(["launchctl", "unload", pp], capture_output=True, timeout=10)
        with open(pp, "wb") as f:
            f.write(new_bytes)
        subprocess.run(["launchctl", "load", pp], capture_output=True, timeout=10)
        say(f"synced {meta['label']}")
    return len(registered)


def _is_loaded(label):
    try:
        result = subprocess.run(
            ["launchctl", "list", label], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False
