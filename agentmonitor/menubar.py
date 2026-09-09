"""macOS menu bar app (rumps) for agents and Claude Code sessions."""

import subprocess
import webbrowser

import rumps

from . import launchagents, sessions, terminal

STATUS_RUNNING = "●"   # filled circle
STATUS_STOPPED = "○"   # empty circle
STATUS_ERROR = "◆"     # filled diamond


class AgentMonitorApp(rumps.App):
    def __init__(self, cfg, web_url=None):
        super().__init__("Agents", quit_button=None)
        self.cfg = cfg
        self.web_url = web_url
        self._build_menu()

    # -- menu construction ------------------------------------------
    def _build_menu(self):
        agents = launchagents.get_agents(self.cfg["launchagent_patterns"])
        status_map = launchagents.get_status_map()

        groups = {}
        for agent in agents:
            groups.setdefault(launchagents.group_key(agent["label"]), []).append(agent)

        running_count = 0
        menu_items = []
        order = [None] + sorted(k for k in groups if k is not None)
        for key in order:
            group_agents = groups.get(key, [])
            if not group_agents:
                continue
            if key is not None:
                menu_items.append(rumps.MenuItem(f"--- {key.upper()} ---", callback=None))
            for agent in group_agents:
                item, is_running = self._agent_item(agent, status_map)
                running_count += 1 if is_running else 0
                menu_items.append(item)

        self.title = f"{self.cfg['menu_title']} {running_count}/{len(agents)}"

        self.menu.clear()
        self.menu.add(rumps.MenuItem(
            f"{running_count} running / {len(agents)} agents", callback=None
        ))
        self.menu.add(rumps.separator)
        for item in menu_items:
            self.menu.add(item)

        self.menu.add(rumps.separator)
        self.menu.add(self._sessions_menu())
        self.menu.add(rumps.separator)
        if self.web_url:
            self.menu.add(rumps.MenuItem("Open Web Dashboard", callback=self._on_dashboard))
        self.menu.add(rumps.MenuItem("Refresh", callback=self._on_refresh))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self._on_quit))

    def _agent_item(self, agent, status_map):
        label = agent["label"]
        pid, exit_code, is_loaded, is_running, has_error = launchagents.agent_status(
            label, status_map
        )
        name = launchagents.friendly_name(label)

        if is_running:
            status, status_text = STATUS_RUNNING, f"Running (PID {pid})"
        elif has_error:
            status, status_text = STATUS_ERROR, f"Error (exit {exit_code})"
        elif is_loaded:
            status, status_text = STATUS_STOPPED, "Loaded, not running"
        else:
            status, status_text = STATUS_STOPPED, "Not loaded"

        item = rumps.MenuItem(f"{status}  {name}")
        item.add(rumps.MenuItem(f"  Status: {status_text}", callback=None))
        item.add(rumps.MenuItem(
            f"  Schedule: {launchagents.format_schedule(agent['schedule'])}", callback=None
        ))
        item.add(rumps.MenuItem(f"  Label: {label}", callback=None))
        item.add(rumps.separator)

        plist_path = agent["plist_path"]
        if is_running:
            item.add(rumps.MenuItem(
                "  Stop", callback=self._cb(launchagents.stop, label, plist_path, f"Stopped {label}")
            ))
            item.add(rumps.MenuItem(
                "  Restart",
                callback=self._cb(launchagents.restart, label, plist_path, f"Restarted {label}")
            ))
        else:
            item.add(rumps.MenuItem(
                "  Start", callback=self._cb(launchagents.start, label, plist_path, f"Started {label}")
            ))

        item.add(rumps.separator)
        if agent["stdout_log"]:
            item.add(rumps.MenuItem(
                "  Tail Stdout Log", callback=self._tail_cb(agent["stdout_log"])
            ))
        if agent["stderr_log"]:
            item.add(rumps.MenuItem(
                "  Tail Stderr Log", callback=self._tail_cb(agent["stderr_log"])
            ))
        item.add(rumps.MenuItem("  Edit Plist", callback=self._open_cb(plist_path)))
        return item, is_running

    def _sessions_menu(self):
        menu = rumps.MenuItem("Claude Sessions")
        try:
            recent = sessions.list_sessions(
                self.cfg["claude_projects_dir"], limit=self.cfg["menu_sessions"]
            )
        except Exception:
            recent = []
        if not recent:
            menu.add(rumps.MenuItem("No sessions found", callback=None))
            return menu

        term_name = "iTerm2" if terminal.pick_terminal(self.cfg["terminal"]) == "iterm" else "Terminal"
        for s in recent:
            age = sessions.age_str(s["mtime"])
            project = sessions.short_project(s["project"], s["cwd"])
            title = s["title"] if len(s["title"]) <= 60 else s["title"][:57] + "..."
            item = rumps.MenuItem(f"{age} · {project} · {title}")
            item.add(rumps.MenuItem(f"  {s['id']}", callback=None))
            if s["cwd"]:
                item.add(rumps.MenuItem(f"  {s['cwd']}", callback=None))
            item.add(rumps.separator)
            item.add(rumps.MenuItem(
                f"  Resume in {term_name}", callback=self._resume_cb(s)
            ))
            item.add(rumps.MenuItem(
                "  Copy Resume Command", callback=self._copy_cb(s)
            ))
            item.add(rumps.MenuItem(
                "  Reveal Transcript in Finder", callback=self._reveal_cb(s["path"])
            ))
            menu.add(item)
        return menu

    # -- callbacks ---------------------------------------------------
    def _cb(self, fn, label, plist_path, message):
        def callback(_):
            fn(label, plist_path)
            rumps.notification("Agent Monitor", message, "", sound=False)
            self._build_menu()
        return callback

    def _tail_cb(self, log_path):
        def callback(_):
            cmd = f"tail -100f {log_path}"
            terminal.open_in_terminal(cmd, self.cfg["terminal"])
        return callback

    def _open_cb(self, path):
        def callback(_):
            subprocess.run(["open", "-t", path])
        return callback

    def _resume_cb(self, session):
        def callback(_):
            cmd = terminal.resume_command(session["cwd"], session["id"])
            ok, err = terminal.open_in_terminal(cmd, self.cfg["terminal"])
            if not ok:
                rumps.notification("Agent Monitor", "Resume failed", err, sound=False)
        return callback

    def _copy_cb(self, session):
        def callback(_):
            cmd = terminal.resume_command(session["cwd"], session["id"])
            terminal.copy_to_clipboard(cmd)
            rumps.notification("Agent Monitor", "Copied", cmd, sound=False)
        return callback

    def _reveal_cb(self, path):
        def callback(_):
            subprocess.run(["open", "-R", path])
        return callback

    def _on_dashboard(self, _):
        webbrowser.open(self.web_url)

    def _on_refresh(self, _):
        self._build_menu()

    def _on_quit(self, _):
        rumps.quit_application()

    @rumps.timer(30)
    def auto_refresh(self, _):
        self._build_menu()
