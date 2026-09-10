# Corral

A macOS menu bar app, web dashboard, and CLI for running scheduled AI agents and recovering Claude Code sessions.

Corral does three things:

1. **Runs your agents.** Register an agent with a name, a prompt, and a schedule. Corral turns it into a launchd job that survives reboots, keeps its logs, and shows up in your menu bar with live status.
2. **Lets you manage them anywhere.** Start, stop, and restart agents and edit their prompts from the menu bar or a local web dashboard.
3. **Recovers lost Claude Code sessions.** When your laptop closes or restarts and your terminal sessions die, Corral lists every recent session and reopens any of them in iTerm2 or Terminal with one click, in the right directory, via `claude --resume`.

## Requirements

- macOS
- Python 3.9 or newer
- [Claude Code](https://claude.com/claude-code) for the default agent command and the session features
- iTerm2 (optional; falls back to Terminal.app)

## Install the app

```bash
git clone https://github.com/YOURNAME/corral.git
cd corral
./install.sh
```

The installer:

- creates a venv and installs dependencies
- builds `Corral.app` (the menu bar app)
- writes a default config to `~/.config/corral/config.json`
- links the `corral` CLI onto your PATH
- offers to install a LaunchAgent so the app starts at login

Run it without the login item:

```bash
corral             # menu bar app + web dashboard
corral --web-only  # dashboard only, at http://127.0.0.1:8765
```

## The agents folder

Every registered agent lives in `~/.config/corral/agents/<name>/`:

```
~/.config/corral/agents/
  morning-digest/
    agent.json    # schedule, command, workdir, env
    prompt.md     # the prompt passed to the command
    logs/         # one log file per run
```

This folder is the source of truth. `corral agent sync` reads it and generates one launchd plist per agent (labeled `com.corral.agent.<name>`), loading them so they run on schedule. Registered agents always appear in the menu bar and dashboard, and their prompts are always editable in the dashboard's agents view.

Because agents are plain folders, they are easy to back up, commit to a dotfiles repo, or copy to another machine (run `corral agent sync` after copying).

## Registering agents

```bash
# daily at 8:00
corral agent add morning-digest --prompt ./prompt.md --at 08:00

# Fridays at 17:00
corral agent add weekly-report --prompt ./prompt.md --at 17:00 --weekday fri

# every 15 minutes
corral agent add queue-worker --prompt ./prompt.md --every 900

# always running, restarted on exit
corral agent add watcher --prompt ./prompt.md --keep-alive

# no schedule; run manually with `corral run planner`
corral agent add planner --prompt-text "Plan my day from ~/notes/today.md"
```

The default command is `claude -p '{prompt}'`. Override it with `--command`; the placeholders `{prompt}` and `{prompt_file}` are substituted when the agent runs, so any CLI works:

```bash
corral agent add summarizer --prompt ./prompt.md --at 07:30 \
  --command "ollama run qwen3 {prompt}"
```

Other commands:

```bash
corral agent list             # what is registered and when it runs
corral run <name>             # execute once, log to the agent's logs/
corral agent remove <name>    # unload from launchd, keep the folder
corral agent remove <name> --purge   # delete the folder too
corral agent sync             # regenerate plists after editing agent.json
```

## Claude Code plugin

The repo doubles as a Claude Code plugin marketplace. Install it and Claude can register agents for you from a conversation ("add an agent that summarizes my inbox every morning at 8"):

```
/plugin marketplace add YOURNAME/corral
/plugin install corral@corral
```

The plugin ships one skill, `corral-agents`, which knows the folder layout and CLI. To use the skill without the plugin, copy it in directly:

```bash
mkdir -p ~/.claude/skills
cp -R plugin/skills/corral-agents ~/.claude/skills/
```

## Configuration

`~/.config/corral/config.json`. Every key is optional.

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

- `launchagent_patterns`: glob patterns for extra LaunchAgents to show, matched against plist filenames in `~/Library/LaunchAgents`. Corral-registered agents are always shown. An empty list shows everything except Apple's own agents.
- `prompt_dirs`: extra directories scanned for markdown and text files, editable in the dashboard. The agents folder is always included, and files referenced in a plist's `ProgramArguments` are picked up automatically.
- `terminal`: `auto`, `iterm`, or `terminal`. Auto picks iTerm2 when installed.

## How session resume works

Claude Code writes each session transcript to `~/.claude/projects/<project>/<session-id>.jsonl`. Corral reads the head of each transcript to recover the working directory and the opening prompt, then opens a terminal window running:

```bash
cd <project directory> && claude --resume <session-id>
```

Nothing is modified in `~/.claude`. Transcripts are only read.

## Security notes

The web server binds to 127.0.0.1 and should stay there. Its API can start launchd jobs, open terminal windows, and edit files inside your prompt directories, so do not expose the port on a network. File editing is restricted to discovered prompt files; arbitrary paths are rejected.

## License

MIT
