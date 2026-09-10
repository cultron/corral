"""Engine discovery: which harness CLIs are installed and which models they offer.

An engine is a row in the config "engines" table. Beyond "command" and
"model_args" (see config.py), an engine may declare:

  "models":      a static list of model names to offer in the dashboard
  "list_models": a command whose stdout lists models, one per line (the
                 first whitespace-separated token of each line; a header
                 line starting with NAME is skipped), e.g. ["ollama", "list"]

Built-in engines get sensible sources: Claude Code's current model IDs and
aliases, Codex's configured default model, and `ollama list`.
"""

import os
import re
import shutil
import subprocess
import time

from .runner import _augmented_path

# Claude Code accepts full model IDs or the aliases fable/opus/sonnet/haiku.
CLAUDE_MODELS = [
    "claude-fable-5-1", "claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5",
    "fable", "opus", "sonnet", "haiku",
]
CODEX_CONFIG = os.path.expanduser("~/.codex/config.toml")

_LIST_TTL = 60  # seconds to cache list_models output
_list_cache = {}  # tuple(cmd) -> (expires, models)


def takes_model(spec):
    """True if the engine's command has somewhere to put a model name."""
    command = spec.get("command") or []
    if any("{model}" in arg for arg in command):
        return True
    return "{model_args}" in command and bool(spec.get("model_args"))


def describe(cfg):
    """Return [{name, available, path, takes_model, models}] for every engine."""
    path_env = _augmented_path(os.environ.get("PATH", ""))
    out = []
    for name in sorted(cfg["engines"]):
        spec = cfg["engines"][name]
        command = spec.get("command") or []
        exe = shutil.which(command[0], path=path_env) if command else None
        out.append({
            "name": name,
            "available": exe is not None,
            "path": exe,
            "takes_model": takes_model(spec),
            "models": _models(name, spec, exe, path_env) if takes_model(spec) else [],
        })
    return out


def _models(name, spec, exe, path_env):
    models = list(spec.get("models") or [])
    if name == "claude" and not models:
        models = list(CLAUDE_MODELS)
    if name == "codex":
        default = _codex_default_model()
        if default:
            models.insert(0, default)
    cmd = spec.get("list_models")
    if cmd and exe:
        models = _run_list(cmd, path_env) + models
    seen, unique = set(), []
    for m in models:
        if m and m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def _codex_default_model():
    try:
        with open(CODEX_CONFIG) as f:
            for line in f:
                m = re.match(r'^\s*model\s*=\s*"([^"]+)"', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


def _run_list(cmd, path_env):
    key = tuple(cmd)
    cached = _list_cache.get(key)
    if cached and cached[0] > time.time():
        return cached[1]
    models = []
    try:
        env = dict(os.environ, PATH=path_env)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)
        for line in res.stdout.splitlines():
            tok = line.split()
            if not tok or tok[0].upper() == "NAME":
                continue
            models.append(tok[0])
    except Exception:
        return models  # e.g. server still starting; try again next request
    _list_cache[key] = (time.time() + _LIST_TTL, models)
    return models
