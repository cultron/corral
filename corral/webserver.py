"""Local web dashboard. Stdlib only, bound to localhost by default.

The API can start and stop launchd jobs, open terminal windows, and
edit prompt files, so it must never be exposed beyond the local machine.
"""

import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import launchagents, prompts, registry, sessions, terminal

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def make_handler(cfg):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        # -- helpers -------------------------------------------------
        def _send_json(self, data, status=200):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error_json(self, message, status=400):
            self._send_json({"error": message}, status)

        def _read_body(self):
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            try:
                return json.loads(self.rfile.read(length))
            except Exception:
                return {}

        def _agents(self):
            return launchagents.get_agents(cfg["launchagent_patterns"])

        def _find_agent(self, label):
            for a in self._agents():
                if a["label"] == label:
                    return a
            return None

        # -- routing -------------------------------------------------
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)

            if path in ("/", "/index.html"):
                return self._serve_index()
            if path == "/api/agents":
                return self._api_agents()
            if path == "/api/engines":
                return self._send_json(sorted(cfg["engines"]))
            if path == "/api/sessions":
                limit = int(query.get("limit", ["50"])[0])
                return self._send_json(
                    sessions.list_sessions(cfg["claude_projects_dir"], limit=min(limit, 200))
                )
            if path == "/api/prompts":
                return self._send_json(prompts.discover(cfg["prompt_dirs"], self._agents()))
            if path == "/api/prompts/file":
                return self._api_prompt_read(query)
            if path.startswith("/api/agents/") and path.endswith("/log"):
                label = urllib.parse.unquote(path.split("/")[3])
                return self._api_agent_log(label, query)
            self._send_error_json("not found", 404)

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            parts = [urllib.parse.unquote(p) for p in path.split("/") if p]
            # /api/agents/<label>/<action>
            if len(parts) == 4 and parts[:2] == ["api", "agents"]:
                return self._api_agent_action(parts[2], parts[3])
            # /api/sessions/<id>/resume
            if len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] == "resume":
                return self._api_session_resume(parts[2])
            # /api/registry/<name>  (update engine/model)
            if len(parts) == 3 and parts[:2] == ["api", "registry"]:
                return self._api_registry_update(parts[2])
            self._send_error_json("not found", 404)

        def do_PUT(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/prompts/file":
                return self._api_prompt_write()
            self._send_error_json("not found", 404)

        # -- endpoints -----------------------------------------------
        def _serve_index(self):
            try:
                with open(os.path.join(STATIC_DIR, "index.html"), "rb") as f:
                    body = f.read()
            except OSError:
                return self._send_error_json("index.html missing", 500)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _api_agents(self):
            status_map = launchagents.get_status_map()
            out = []
            for a in self._agents():
                pid, exit_code, loaded, running, error = launchagents.agent_status(
                    a["label"], status_map
                )
                entry = {
                    "label": a["label"],
                    "name": launchagents.friendly_name(a["label"]),
                    "group": launchagents.group_key(a["label"]),
                    "schedule": launchagents.format_schedule(a["schedule"]),
                    "keep_alive": a["keep_alive"],
                    "pid": pid,
                    "exit_code": exit_code,
                    "loaded": loaded,
                    "running": running,
                    "error": error,
                    "stdout_log": a["stdout_log"],
                    "stderr_log": a["stderr_log"],
                    "plist_path": a["plist_path"],
                }
                if a["label"].startswith(registry.LABEL_PREFIX):
                    name = a["label"][len(registry.LABEL_PREFIX):]
                    meta = registry.load(name)
                    if meta and "config" in meta:
                        rcfg = meta["config"]
                        entry["registry_name"] = name
                        entry["engine"] = rcfg.get("engine") or "claude"
                        entry["model"] = rcfg.get("model") or ""
                        entry["has_command"] = bool(rcfg.get("command"))
                        entry["is_service"] = registry.is_service(rcfg)
                out.append(entry)
            self._send_json(out)

        def _api_registry_update(self, name):
            body = self._read_body()
            fields = {}
            if "engine" in body:
                engine = body["engine"] or None
                if engine and engine not in cfg["engines"]:
                    return self._send_error_json(f"unknown engine {engine!r}", 400)
                fields["engine"] = engine
            if "model" in body:
                fields["model"] = body["model"] or None
            if not fields:
                return self._send_error_json("nothing to update", 400)
            try:
                new_cfg = registry.update_fields(name, **fields)
            except registry.RegistryError as e:
                return self._send_error_json(str(e), 404)
            # Scheduled agents read agent.json on their next run; only a
            # running service needs a bounce to pick the change up.
            restarted = False
            if registry.is_service(new_cfg):
                restarted = registry.restart_job(name)
            self._send_json({"ok": True, "restarted": restarted})

        def _api_agent_action(self, label, action):
            agent = self._find_agent(label)
            if agent is None:
                return self._send_error_json("unknown agent", 404)
            if action == "start":
                launchagents.start(label, agent["plist_path"])
            elif action == "stop":
                launchagents.stop(label, agent["plist_path"])
            elif action == "restart":
                launchagents.restart(label, agent["plist_path"])
            else:
                return self._send_error_json("unknown action", 400)
            self._send_json({"ok": True})

        def _api_agent_log(self, label, query):
            agent = self._find_agent(label)
            if agent is None:
                return self._send_error_json("unknown agent", 404)
            which = query.get("which", ["stdout"])[0]
            log_path = agent["stderr_log"] if which == "stderr" else agent["stdout_log"]
            lines = min(int(query.get("lines", ["200"])[0]), 2000)
            content = launchagents.tail_file(log_path, lines)
            if content is None:
                return self._send_error_json(f"log not found: {log_path}", 404)
            self._send_json({"path": log_path, "content": content})

        def _api_session_resume(self, session_id):
            for s in sessions.list_sessions(cfg["claude_projects_dir"], limit=200):
                if s["id"] == session_id:
                    cmd = terminal.resume_command(s["cwd"], session_id)
                    ok, err = terminal.open_in_terminal(cmd, cfg["terminal"])
                    if ok:
                        return self._send_json({"ok": True, "command": cmd})
                    return self._send_error_json(f"terminal failed: {err}", 500)
            self._send_error_json("unknown session", 404)

        def _api_prompt_read(self, query):
            path = query.get("path", [""])[0]
            if not prompts.is_allowed(path, cfg["prompt_dirs"], self._agents()):
                return self._send_error_json("path not allowed", 403)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError as e:
                return self._send_error_json(str(e), 404)
            self._send_json({"path": path, "content": content})

        def _api_prompt_write(self):
            body = self._read_body()
            path = body.get("path", "")
            content = body.get("content")
            if content is None:
                return self._send_error_json("missing content", 400)
            if not prompts.is_allowed(path, cfg["prompt_dirs"], self._agents()):
                return self._send_error_json("path not allowed", 403)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            except OSError as e:
                return self._send_error_json(str(e), 500)
            self._send_json({"ok": True})

    return Handler


def start_in_thread(cfg):
    """Start the dashboard server on a daemon thread.

    Returns the server URL, or None if the port is taken (for example a
    second copy of the app is already running).
    """
    try:
        server = ThreadingHTTPServer(
            (cfg["web_host"], cfg["web_port"]), make_handler(cfg)
        )
    except OSError as e:
        print(f"corral: web dashboard not started: {e}")
        return None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"http://{cfg['web_host']}:{cfg['web_port']}"
