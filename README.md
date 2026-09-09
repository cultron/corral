# Agent Monitor

A macOS menu bar app and local web dashboard for managing launchd agents and Claude Code sessions.

If you run scheduled Claude Code agents through launchd, or you lose terminal sessions when your laptop sleeps or restarts, this tool solves both problems. It shows every agent's status in the menu bar, lets you edit their prompts from a browser, and reopens any recent Claude Code session in iTerm2 or Terminal with one click.

## Features

**Menu bar app**
- Shows all your LaunchAgents with live status (running, stopped, errored), grouped by agent name
- Start, stop, and restart agents; tail their logs in a terminal window
- A Claude Sessions dropdown listing your most recent Claude Code sessions with their project and last prompt. Click one to reopen it in iTerm2 (or Terminal) in the right directory via `claude --resume`

**Web dashboard** (localhost only)
- Agents tab: same controls as the menu bar, plus an in-browser log viewer
- Sessions tab: browse recent sessions across all projects, resume any of them, or copy the resume command
- Prompts tab: edit the markdown prompt files your agents run, right in the browser

## Requirements

- macOS
- Python 3.9 or newer
- [Claude Code](https://claude.com/claude-code) for the sessions features
- iTerm2 (optional; falls back to Terminal.app)

## Install

```bash
git clone https://github.com/YOURNAME/claude-agent-monitor.git
cd claude-agent-monitor
./install.sh
```

The installer creates a venv, builds `AgentMonitor.app`, writes a default config, and offers to install a LaunchAgent so the app starts at login.

Run it manually without installing the LaunchAgent:

```bash
./venv/bin/python3 -m agentmonitor            # menu bar + web dashboard
./venv/bin/python3 -m agentmonitor --web-only # dashboard only, no menu bar
```

The dashboard is at http://127.0.0.1:8765 by default.

## Configuration

Config lives at `~/.config/agent-monitor/config.json`. Every key is optional.

```json
{
  "launchagent_patterns": ["com.mycompany.*"],
  "prompt_dirs": ["~/my-agents/prompts"],
  "claude_projects_dir": "~/.claude/projects",
  "web_host": "127.0.0.1",
  "web_port": 8765,
  "terminal": "auto",
  "menu_sessions": 12,
  "menu_title": "A"
}
```

- `launchagent_patterns`: glob patterns matched against plist filenames in `~/Library/LaunchAgents`. An empty list shows everything except Apple's own agents.
- `prompt_dirs`: directories scanned for markdown and text files, editable in the Prompts tab. Files referenced directly in an agent's plist `ProgramArguments` are picked up automatically.
- `terminal`: `auto`, `iterm`, or `terminal`. Auto picks iTerm2 when installed.

## How session resume works

Claude Code writes each session transcript to `~/.claude/projects/<project>/<session-id>.jsonl`. Agent Monitor reads the head of each transcript to recover the working directory and the first prompt, then opens a terminal window running:

```bash
cd <project directory> && claude --resume <session-id>
```

Nothing is modified in `~/.claude`. Transcripts are only read.

## Security notes

The web server binds to 127.0.0.1 and should stay there. Its API can start launchd jobs, open terminal windows, and edit files inside your configured prompt directories, so do not expose the port on a network. File editing is restricted to discovered prompt files; arbitrary paths are rejected.

## License

MIT
