"""Discovery of agent prompt/context files editable in the dashboard.

Two sources: configured prompt directories (scanned recursively for
markdown and text files) and file paths that appear directly in an
agent's plist ProgramArguments. Only discovered files may be read or
written through the web API.
"""

import os

EDITABLE_EXTENSIONS = (".md", ".txt", ".markdown")
MAX_FILES = 500


def discover(prompt_dirs, agents):
    """Return a list of {path, name, source, agent_label, size, mtime}."""
    seen = {}

    for agent in agents:
        for arg in agent.get("program_arguments", []):
            if arg.lower().endswith(EDITABLE_EXTENSIONS) and os.path.isfile(arg):
                real = os.path.realpath(arg)
                seen[real] = _entry(real, "plist", agent["label"])

    from .registry import AGENTS_DIR, LABEL_PREFIX
    registry_root = os.path.realpath(AGENTS_DIR)

    for d in prompt_dirs:
        root = os.path.expanduser(d)
        if not os.path.isdir(root):
            continue
        is_registry = os.path.realpath(root) == registry_root
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [n for n in dirnames if not n.startswith(".")]
            for name in sorted(filenames):
                if not name.lower().endswith(EDITABLE_EXTENSIONS):
                    continue
                real = os.path.realpath(os.path.join(dirpath, name))
                if real not in seen:
                    # First subdirectory under the prompt dir names the
                    # agent group, e.g. prompts/susie/brief.md -> susie.
                    # Inside the registry it names the agent itself.
                    rel = os.path.relpath(real, os.path.realpath(root))
                    group = rel.split(os.sep)[0] if os.sep in rel else None
                    if is_registry and group:
                        seen[real] = _entry(real, "registry", LABEL_PREFIX + group)
                    else:
                        seen[real] = _entry(real, "prompt_dir", None, group)
                if len(seen) >= MAX_FILES:
                    break

    entries = sorted(seen.values(), key=lambda e: e["path"])
    return entries


def _entry(path, source, agent_label, group=None):
    try:
        stat = os.stat(path)
        size, mtime = stat.st_size, stat.st_mtime
    except OSError:
        size, mtime = 0, 0
    return {
        "path": path,
        "name": os.path.basename(path),
        "source": source,
        "agent_label": agent_label,
        "group": group,
        "size": size,
        "mtime": mtime,
    }


def is_allowed(path, prompt_dirs, agents):
    """A path is editable only if discovery would find it."""
    real = os.path.realpath(path)
    allowed = {e["path"] for e in discover(prompt_dirs, agents)}
    return real in allowed
