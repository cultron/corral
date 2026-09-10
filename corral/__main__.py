"""Corral CLI.

corral                     menu bar app + web dashboard
corral --web-only          web dashboard only
corral agent add NAME      register an agent (see flags below)
corral agent list          show registered agents
corral agent remove NAME   unload an agent (--purge deletes its folder)
corral agent sync          regenerate and reload launchd plists
corral run NAME            execute a registered agent once (used by launchd)
"""

import argparse
import json
import sys

from . import config, registry

WEEKDAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


def main():
    parser = argparse.ArgumentParser(prog="corral", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--web-only", action="store_true",
                        help="run the web dashboard without the menu bar app")
    sub = parser.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="execute a registered agent once")
    run_p.add_argument("name")

    agent_p = sub.add_parser("agent", help="manage registered agents")
    agent_sub = agent_p.add_subparsers(dest="agent_cmd", required=True)

    add_p = agent_sub.add_parser("add", help="register a new agent")
    add_p.add_argument("name", help="lowercase letters, digits, - and _")
    add_p.add_argument("--prompt", help="path to a prompt file to copy in")
    add_p.add_argument("--prompt-text", help="inline prompt text")
    add_p.add_argument("--command", help="shell-style command; {prompt} and "
                       "{prompt_file} are substituted (default: claude -p '{prompt}')")
    add_p.add_argument("--at", help="daily run time, HH:MM")
    add_p.add_argument("--weekday", help="restrict --at to a weekday (mon..sun)")
    add_p.add_argument("--every", type=int, metavar="SECONDS",
                       help="run on an interval instead of a calendar time")
    add_p.add_argument("--keep-alive", action="store_true",
                       help="run continuously; restart on exit")
    add_p.add_argument("--workdir", help="working directory for runs")
    add_p.add_argument("--env", action="append", default=[], metavar="K=V")
    add_p.add_argument("--extra", metavar="JSON",
                       help="extra launchd keys merged into the plist, "
                       "e.g. '{\"WatchPaths\": [\"/some/file\"]}'")
    add_p.add_argument("--description", default="")
    add_p.add_argument("--no-sync", action="store_true",
                       help="register only; do not install the launchd plist yet")

    agent_sub.add_parser("list", help="show registered agents")

    rm_p = agent_sub.add_parser("remove", help="unload an agent's plist")
    rm_p.add_argument("name")
    rm_p.add_argument("--purge", action="store_true",
                      help="also delete the agent folder and its logs")

    agent_sub.add_parser("sync", help="regenerate and reload all plists")

    args = parser.parse_args()

    if args.cmd == "run":
        from . import runner
        sys.exit(runner.run(args.name))
    if args.cmd == "agent":
        sys.exit(agent_command(args))
    serve(args.web_only)


def agent_command(args):
    try:
        if args.agent_cmd == "add":
            return agent_add(args)
        if args.agent_cmd == "list":
            return agent_list()
        if args.agent_cmd == "remove":
            registry.remove(args.name, purge=args.purge)
            print(f"removed {args.name}" + (" (purged)" if args.purge else
                  f" (folder kept at {registry.agent_dir(args.name)})"))
            return 0
        if args.agent_cmd == "sync":
            n = registry.sync()
            print(f"{n} agent(s) synced")
            return 0
    except registry.RegistryError as e:
        print(f"corral: {e}", file=sys.stderr)
        return 1


def agent_add(args):
    import shlex

    prompt_text = args.prompt_text or ""
    if args.prompt:
        with open(args.prompt) as f:
            prompt_text = f.read()

    schedule = None
    if args.at:
        hour, minute = args.at.split(":")
        schedule = {"Hour": int(hour), "Minute": int(minute)}
        if args.weekday:
            day = WEEKDAYS.get(args.weekday.lower()[:3])
            if day is None:
                print(f"corral: unknown weekday {args.weekday!r}", file=sys.stderr)
                return 1
            schedule["Weekday"] = day

    env = {}
    for pair in args.env:
        if "=" not in pair:
            print(f"corral: --env expects K=V, got {pair!r}", file=sys.stderr)
            return 1
        k, v = pair.split("=", 1)
        env[k] = v

    extra = None
    if args.extra:
        try:
            extra = json.loads(args.extra)
        except ValueError as e:
            print(f"corral: --extra is not valid JSON: {e}", file=sys.stderr)
            return 1

    meta = registry.add(
        args.name,
        prompt_text=prompt_text,
        command=shlex.split(args.command) if args.command else None,
        schedule=schedule,
        interval_seconds=args.every,
        keep_alive=args.keep_alive,
        workdir=args.workdir,
        env=env,
        description=args.description,
        launchd_extra=extra,
    )
    print(f"registered {args.name} at {meta['dir']}")
    if args.no_sync:
        print("run `corral agent sync` to install its launchd plist")
    else:
        registry.sync(quiet=True)
        print(f"loaded {meta['label']}")
    return 0


def agent_list():
    agents = registry.list_registered()
    if not agents:
        print(f"no registered agents in {registry.AGENTS_DIR}")
        return 0
    for a in agents:
        if "config" not in a:
            print(f"{a['name']:24} BROKEN: {a.get('error')}")
            continue
        cfg = a["config"]
        if cfg.get("schedule"):
            when = json.dumps(cfg["schedule"])
        elif cfg.get("interval_seconds"):
            when = f"every {cfg['interval_seconds']}s"
        elif cfg.get("keep_alive"):
            when = "keep-alive"
        else:
            when = "manual"
        print(f"{a['name']:24} {when:28} {a['dir']}")
    return 0


def serve(web_only):
    from . import webserver
    cfg = config.load_config()
    web_url = webserver.start_in_thread(cfg)

    if web_only:
        if web_url is None:
            sys.exit(1)
        print(f"corral dashboard: {web_url}")
        import threading
        threading.Event().wait()
        return

    from .menubar import CorralApp
    CorralApp(cfg, web_url=web_url).run()


if __name__ == "__main__":
    main()
