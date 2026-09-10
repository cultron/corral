"""Discovery of resumable engine sessions.

Claude Code writes <uuid>.jsonl transcripts under ~/.claude/projects/<project>/;
Codex writes rollout-<stamp>-<uuid>.jsonl under ~/.codex/sessions/YYYY/MM/DD/.
We read only the head of each file to extract a title and working
directory, and cache by (path, mtime) so periodic refreshes stay cheap.
Every session dict carries an "engine" key ("claude" or "codex").
"""

import glob
import html
import json
import os
import time

# Read at most this much of each transcript head when extracting metadata.
_HEAD_BYTES = 262144

_cache = {}  # path -> (mtime, meta dict)


def list_sessions(cfg, limit=50):
    """Most recent sessions across engines, newest first."""
    files = []
    claude_root = os.path.expanduser(cfg.get("claude_projects_dir") or "")
    if claude_root:
        for path in glob.glob(os.path.join(claude_root, "*", "*.jsonl")):
            # agent-*.jsonl files are subagent transcripts, not resumable sessions
            if os.path.basename(path).startswith("agent-"):
                continue
            files.append(("claude", path))
    codex_root = os.path.expanduser(cfg.get("codex_sessions_dir") or "")
    if codex_root:
        for path in glob.glob(os.path.join(codex_root, "*", "*", "*", "rollout-*.jsonl")):
            files.append(("codex", path))

    stamped = []
    for engine, path in files:
        try:
            stamped.append((os.path.getmtime(path), engine, path))
        except OSError:
            continue
    stamped.sort(reverse=True)

    sessions = []
    for mtime, engine, path in stamped:
        parser = _parse_codex_head if engine == "codex" else _parse_head
        meta = parser(path, mtime)
        if meta is None:
            continue
        sessions.append(meta)
        if len(sessions) >= limit:
            break
    return sessions


def _parse_codex_head(path, mtime):
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, "rb") as f:
            head = f.read(_HEAD_BYTES)
    except OSError:
        return None

    session_id = cwd = branch = first_user_text = None
    for raw in head.split(b"\n"):
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        if d.get("type") == "session_meta":
            source = payload.get("source")
            if isinstance(source, dict) and "subagent" in source:
                meta = None  # spawned sub-thread, not resumable on its own
                _cache[path] = (mtime, meta)
                return meta
            session_id = payload.get("id") or payload.get("session_id")
            cwd = payload.get("cwd")
            git = payload.get("git") if isinstance(payload.get("git"), dict) else {}
            branch = git.get("branch")
        elif (d.get("type") == "response_item" and payload.get("type") == "message"
              and payload.get("role") == "user" and first_user_text is None):
            for block in payload.get("content") or []:
                if isinstance(block, dict) and block.get("type") in ("input_text", "text"):
                    text = (block.get("text") or "").strip()
                    if text and not text.startswith("<"):
                        first_user_text = text
                        break
        if session_id and cwd and first_user_text:
            break
    if not session_id:
        _cache[path] = (mtime, None)
        return None

    # Codex Desktop transcripts carry HTML entities such as &#x20;
    title = " ".join(html.unescape(first_user_text or "(no prompt captured)").split())
    if len(title) > 90:
        title = title[:87] + "..."
    meta = {
        "engine": "codex",
        "id": session_id,
        "path": path,
        "project": os.path.basename((cwd or "").rstrip("/")) or "codex",
        "cwd": cwd,
        "branch": branch,
        "title": title,
        "mtime": mtime,
        "size": os.path.getsize(path) if os.path.exists(path) else 0,
    }
    _cache[path] = (mtime, meta)
    return meta


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
        "engine": "claude",
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
