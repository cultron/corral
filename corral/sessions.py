"""Discovery of Claude Code sessions from ~/.claude/projects.

Each session is a <uuid>.jsonl transcript inside a per-project folder.
We read only the head of each file to extract a title and working
directory, and cache by (path, mtime) so periodic refreshes stay cheap.
"""

import glob
import json
import os
import time

# Read at most this much of each transcript head when extracting metadata.
_HEAD_BYTES = 262144

_cache = {}  # path -> (mtime, meta dict)


def list_sessions(claude_projects_dir, limit=50):
    root = os.path.expanduser(claude_projects_dir)
    files = []
    for path in glob.glob(os.path.join(root, "*", "*.jsonl")):
        base = os.path.basename(path)
        # agent-*.jsonl files are subagent transcripts, not resumable sessions
        if base.startswith("agent-"):
            continue
        try:
            files.append((os.path.getmtime(path), path))
        except OSError:
            continue
    files.sort(reverse=True)

    sessions = []
    for mtime, path in files[:limit]:
        meta = _parse_head(path, mtime)
        if meta is None:
            continue
        sessions.append(meta)
    return sessions


def _parse_head(path, mtime):
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]

    session_id = os.path.basename(path)[: -len(".jsonl")]
    cwd = None
    branch = None
    summary = None
    first_user_text = None
    last_prompt = None

    try:
        with open(path, "rb") as f:
            head = f.read(_HEAD_BYTES)
    except OSError:
        return None

    for raw in head.split(b"\n"):
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue  # final line may be truncated by the head read
        if cwd is None and d.get("cwd"):
            cwd = d["cwd"]
        if branch is None and d.get("gitBranch"):
            branch = d["gitBranch"]
        dtype = d.get("type")
        if summary is None and dtype == "summary" and d.get("summary"):
            summary = d["summary"]
        if last_prompt is None and dtype == "last-prompt" and d.get("prompt"):
            last_prompt = d["prompt"]
        if first_user_text is None and dtype == "user" and not d.get("isMeta") \
                and not d.get("isSidechain"):
            text = _message_text(d.get("message"))
            if text:
                first_user_text = text
        if cwd and (summary or first_user_text):
            break

    title = summary or first_user_text or last_prompt or "(no prompt captured)"
    title = " ".join(title.split())
    if len(title) > 90:
        title = title[:87] + "..."

    meta = {
        "id": session_id,
        "path": path,
        "project": os.path.basename(os.path.dirname(path)),
        "cwd": cwd,
        "branch": branch,
        "title": title,
        "mtime": mtime,
        "size": os.path.getsize(path) if os.path.exists(path) else 0,
    }
    _cache[path] = (mtime, meta)
    return meta


def _message_text(message):
    """Extract plain text from a transcript user-message record."""
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    text = None
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                break
    if not text:
        return None
    text = text.strip()
    # Skip harness-injected wrappers like <command-name> or <system-reminder>
    if text.startswith("<"):
        return None
    return text


def age_str(mtime):
    delta = time.time() - mtime
    if delta < 3600:
        return f"{max(1, int(delta // 60))}m"
    if delta < 86400:
        return f"{int(delta // 3600)}h"
    return f"{int(delta // 86400)}d"


def short_project(project_dirname, cwd):
    """A compact project label for menus: the last path component."""
    if cwd:
        return os.path.basename(cwd.rstrip("/")) or cwd
    return project_dirname.split("-")[-1] or project_dirname
