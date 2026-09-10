---
name: corral-agents
description: Register, list, update, or remove Corral agents (scheduled AI agents managed by launchd on macOS). Use when the user wants to add a new agent, schedule a recurring agent, change an agent's prompt or schedule, or remove an agent, and mentions Corral or has Corral installed.
---

# Managing Corral agents

Corral keeps every registered agent in its own folder under `~/.config/corral/agents/<name>/`:

- `agent.json` holds the schedule, command, working directory, and env vars
- `prompt.md` holds the prompt passed to the agent's command
- `logs/` collects one log file per run

The `corral agent sync` command turns these folders into launchd plists labeled `com.corral.agent.<name>`, so agents survive reboots and appear in the Corral menu bar app and web dashboard.

## Finding the CLI

Try `corral` on the PATH first. If missing, look for the repo and use its venv directly:

```bash
which corral || ls ~/projects/corral/venv/bin/python3
# fallback invocation:
cd ~/projects/corral && ./venv/bin/python3 -m corral <args>
```

## Adding an agent

1. Ask for anything not already given: the agent's name (lowercase, hyphens), what it should do (this becomes the prompt), and when it should run.
2. Write the prompt to a temp file, then register:

```bash
corral agent add morning-digest --prompt /tmp/prompt.md --at 08:00
corral agent add weekly-report --prompt /tmp/prompt.md --at 17:00 --weekday fri
corral agent add queue-worker --prompt /tmp/prompt.md --every 900
corral agent add watcher --prompt /tmp/prompt.md --keep-alive
```

Useful flags: `--engine claude|codex|ollama|aider|dsh` and `--model NAME` pick the harness and model (default engine is claude); `--command "..."` overrides the engine template entirely (the placeholders `{prompt}`, `{prompt_file}`, and `{model}` are substituted at run time); `--workdir DIR` for where the command runs; `--env K=V` (repeatable); `--description "..."`.

To change an agent's engine or model later, edit `engine`/`model` in its `agent.json` (no sync needed; the runner reads it at run time), or use the gear chip on the agent's row in the web dashboard. Wrapper scripts receive the choice as `CORRAL_ENGINE` / `CORRAL_MODEL` env vars.

3. `add` installs and loads the launchd plist automatically. Verify with:

```bash
corral agent list
launchctl list | grep com.corral.agent
```

4. Offer a test run: `corral run <name>`, then check the newest file in `~/.config/corral/agents/<name>/logs/`.

## Editing an agent

Edit `~/.config/corral/agents/<name>/prompt.md` or `agent.json` directly, then run `corral agent sync` if `agent.json` changed (prompt-only edits need no sync). Confirm the schedule change with `corral agent list`.

## Removing an agent

```bash
corral agent remove <name>          # unloads launchd, keeps the folder
corral agent remove <name> --purge  # also deletes the folder and logs
```

Ask before using `--purge`; it deletes the prompt and run history.

## Daemons and advanced launchd options

Agents can be long-running services. `--keep-alive` agents are exec'd directly so launchd supervises the real process. For launchd keys the CLI does not model, pass raw JSON with `--extra`, merged into the generated plist verbatim:

```bash
corral agent add inbox-alert --command "bash ~/scripts/notify.sh" \
  --extra '{"WatchPaths": ["/Users/me/inbox/ALERT.md"], "ThrottleInterval": 60}'
corral agent add api-server --command "node ~/api/server.js" \
  --extra '{"KeepAlive": {"SuccessfulExit": false}, "RunAtLoad": true}'
```

## Notes

- Schedules use launchd. `--at HH:MM` runs daily, `--weekday` restricts it, `--every SECONDS` uses a fixed interval, `--keep-alive` restarts the process whenever it exits.
- The default command runs Claude Code headless (`claude -p`). Any CLI works: set `--command` to use a different tool, with `{prompt}` or `{prompt_file}` for the prompt.
- A `manual` agent (no schedule flags) only runs via `corral run <name>`.
- `corral agent sync` only reloads agents whose plist changed; running daemons are not bounced by unrelated adds.
