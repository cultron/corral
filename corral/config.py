"""Configuration loading.

Config lives at ~/.config/corral/config.json. Missing keys fall
back to defaults, so a partial config file is fine.
"""

import json
import os

CONFIG_PATH = os.path.expanduser("~/.config/corral/config.json")

DEFAULTS = {
    # Glob patterns matched against LaunchAgent labels (the plist filename
    # without .plist). Empty list means: show every plist in
    # ~/Library/LaunchAgents except Apple's own.
    "launchagent_patterns": [],
    # Directories scanned recursively for prompt/context files (.md, .txt)
    # editable in the web dashboard. Files referenced directly in an
    # agent's plist ProgramArguments are picked up automatically.
    "prompt_dirs": [],
    # Where Claude Code stores session transcripts.
    "claude_projects_dir": "~/.claude/projects",
    # Web dashboard bind address. Keep this on localhost: the API can
    # start processes and edit files.
    "web_host": "127.0.0.1",
    "web_port": 8765,
    # "auto" picks iTerm2 if installed, otherwise Terminal.app.
    # Set "iterm" or "terminal" to force one.
    "terminal": "auto",
    # How many recent sessions to show in the menu bar dropdown.
    "menu_sessions": 12,
    # Menu bar title prefix.
    "menu_title": "A",
    # Engines an agent can run on. An agent with no explicit "command"
    # uses its "engine" (default claude) resolved through this table.
    # {model_args} expands to model_args when the agent has a model,
    # and disappears otherwise. {model} and {prompt}/{prompt_file} are
    # substituted at run time. Add or override engines in your config.
    "engines": {
        "claude": {
            "command": ["claude", "-p", "{model_args}", "{prompt}"],
            "model_args": ["--model", "{model}"],
        },
        "codex": {
            "command": ["codex", "exec", "{model_args}", "{prompt}"],
            "model_args": ["--model", "{model}"],
        },
        "ollama": {
            "command": ["ollama", "run", "{model}", "{prompt}"],
        },
        "aider": {
            "command": ["aider", "{model_args}", "--message", "{prompt}", "--yes-always"],
            "model_args": ["--model", "{model}"],
        },
        # DeepSeek Harness picks its model in the dsh profile config,
        # so there is no model flag here.
        "dsh": {
            "command": ["dsh", "--profile", "headless", "{prompt}"],
        },
    },
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"corral: bad config at {CONFIG_PATH}: {e}")
    # User engines extend the built-ins instead of replacing the table
    engines = dict(DEFAULTS["engines"])
    engines.update(cfg.get("engines") or {})
    cfg["engines"] = engines
    # Registered agents are always visible and their prompts editable,
    # regardless of the user's pattern list.
    from .registry import AGENTS_DIR, LABEL_PREFIX
    cfg["prompt_dirs"] = list(cfg["prompt_dirs"]) + [AGENTS_DIR]
    if cfg["launchagent_patterns"]:
        cfg["launchagent_patterns"] = list(cfg["launchagent_patterns"]) + [LABEL_PREFIX + "*"]
    return cfg


def write_default_config():
    """Create the config file with defaults if it does not exist."""
    if os.path.exists(CONFIG_PATH):
        return False
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULTS, f, indent=2)
    return True
