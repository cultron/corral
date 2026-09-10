"""Executes a registered agent. This is what the generated plists run."""

import datetime
import os
import subprocess
import sys

from . import config, registry


class EngineError(Exception):
    pass


def build_argv(cfg, engines, prompt, prompt_file):
    """Resolve the agent's argv.

    An explicit "command" wins. Otherwise the agent's "engine" (default
    claude) is looked up in the engines table. {model_args} expands to
    the engine's model_args when a model is set and disappears
    otherwise; {model}, {prompt}, and {prompt_file} are substituted
    everywhere.
    """
    model = cfg.get("model") or ""
    command = cfg.get("command")
    if not command:
        engine = cfg.get("engine") or "claude"
        spec = engines.get(engine)
        if spec is None:
            raise EngineError(
                f"unknown engine {engine!r}; known: {', '.join(sorted(engines))}"
            )
        model = model or spec.get("default_model") or ""
        command = []
        for arg in spec["command"]:
            if arg == "{model_args}":
                if model:
                    command.extend(spec.get("model_args", []))
                continue
            command.append(arg)

    argv = []
    for arg in command:
        if "{model}" in arg and not model:
            raise EngineError(
                "this agent's command needs a model; set \"model\" in agent.json"
            )
        arg = arg.replace("{model}", model)
        arg = arg.replace("{prompt_file}", prompt_file or "")
        arg = arg.replace("{prompt}", prompt)
        argv.append(arg)
    return argv


def run(name):
    meta = registry.load(name)
    if meta is None or "config" not in meta:
        print(f"corral: no registered agent named {name!r}", file=sys.stderr)
        return 2
    cfg = meta["config"]

    prompt = ""
    if meta["prompt_path"]:
        with open(meta["prompt_path"]) as f:
            prompt = f.read()

    try:
        argv = build_argv(cfg, config.load_config()["engines"], prompt, meta["prompt_path"])
    except EngineError as e:
        print(f"corral run {name}: {e}", file=sys.stderr)
        return 2

    workdir = os.path.expanduser(cfg.get("workdir") or meta["dir"])
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (cfg.get("env") or {}).items()})
    # Wrapper scripts route on these, so an engine change in the
    # dashboard reaches agents that run through their own shell script.
    env["CORRAL_AGENT"] = name
    env["CORRAL_ENGINE"] = cfg.get("engine") or "claude"
    if cfg.get("model"):
        env["CORRAL_MODEL"] = cfg["model"]

    # Services (keep-alive, or anything with a KeepAlive override) replace
    # this process entirely, so launchd signals the daemon itself and
    # stop/restart cannot orphan a child. Output goes to the launchd logs.
    if registry.is_service(cfg):
        os.chdir(workdir)
        os.execvpe(argv[0], argv, env)

    logs_dir = os.path.join(meta["dir"], "logs")
    os.makedirs(logs_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join(logs_dir, f"run-{stamp}.log")

    with open(log_path, "w") as log:
        log.write(f"# corral run {name} at {stamp}\n# command: {argv[0]} ...\n\n")
        log.flush()
        result = subprocess.run(
            argv, cwd=workdir, env=env, stdout=log, stderr=subprocess.STDOUT
        )
    print(f"corral run {name}: exit {result.returncode}, log {log_path}")
    return result.returncode
