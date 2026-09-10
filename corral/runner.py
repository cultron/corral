"""Executes a registered agent. This is what the generated plists run."""

import datetime
import os
import subprocess
import sys

from . import registry


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

    argv = []
    for arg in (cfg.get("command") or registry.DEFAULT_COMMAND):
        arg = arg.replace("{prompt_file}", meta["prompt_path"] or "")
        arg = arg.replace("{prompt}", prompt)
        argv.append(arg)

    workdir = os.path.expanduser(cfg.get("workdir") or meta["dir"])
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (cfg.get("env") or {}).items()})

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
