# Roadmap

This file stubs out planned work. Each item lists the problem, the intended shape, and its current status. Open an issue to discuss an item before starting a large change.

## Agent installation system

**Problem:** agents are shareable in principle (each one is a plain folder), but installing someone else's agent means copying files by hand and guessing at required environment variables.

**Intended shape:** a `corral agent install <git-url|path>` command that:

1. Clones or copies an agent package into `~/.config/corral/agents/<name>/`.
2. Reads a manifest that declares required environment variables and prompts for them.
3. Runs an optional setup step, such as `npm install`, declared in the manifest.
4. Runs `corral agent sync`.

A curated catalog of community agent packages can follow once the installer exists.

**Status:** not started. The registry and sync layers it builds on are shipped.

## Session providers beyond Claude Code

**Problem:** session recovery only reads Claude Code transcripts. Codex keeps equivalent resumable sessions in `~/.codex/sessions`, DeepSeek Harness has session state with a `--resume` flag, and opencode and crush keep their own stores.

**Intended shape:** a provider interface with two functions per provider, `list_sessions()` and `resume_command(session)`. Providers register the store they read and the command they emit. Sessions gain a provider badge in the dashboard and the menu bar.

**Status:** not started. `corral/sessions.py` is already isolated from the rest of the app, so the refactor is contained.

## DeepSeek Harness setup guide and MCP bridge

**Problem:** the `dsh` engine is shipped, but a working DeepSeek agent needs credentials and, for agents that read real data, the MCP tool bridge. Neither is documented here yet.

**Intended shape:** a documented setup path:

1. Store `DEEPSEEK_API_KEY` through the dsh credentials service (`dsh web`, Models page) so launchd-run agents can authenticate.
2. Configure MCP servers (calendar, email, Slack) in `~/.dsh/mcp.json` through the `dsh-mcp-client` plugin.
3. Set allow rules for the tools each agent uses, because ask-mode permission prompts hang unattended runs.
4. Verify with a scheduled agent that reads real data.

**Status:** engine shipped and tested up to the credential step. The MCP bridge carries only the Tools capability as of August 2026, which covers common calendar and email servers.

## Corral plugin system

**Problem:** extending Corral itself (new dashboard views, notification backends, alternate session providers) currently means editing core code.

**Intended shape:** undecided, and deliberately deferred. The rule: no plugin API until at least two concrete consumers exist. The session provider interface above is the first candidate; a notification backend would be the second.

**Status:** deferred by design.

## Engine health checks

**Problem:** an agent can be scheduled on an engine whose binary is missing or whose credentials are absent, and the failure only surfaces in the run log after the fact.

**Intended shape:** a preflight check per engine (binary on PATH, credential present) shown as a warning on the agent's dashboard row and menu bar entry, and a `corral doctor` command that runs all checks at once.

**Status:** not started.

## Smaller items

- Dashboard screenshots in the README.
- A distinctive menu bar glyph option beyond the text title.
- Editing schedules from the dashboard, not just the CLI and `agent.json`.
- A `corral agent pause NAME` command that unloads a job without removing it.
