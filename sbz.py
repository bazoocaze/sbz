#!/usr/bin/env python3
"""sbz — Sandboxed command execution via bubblewrap."""

import argparse
import os
import sys
from pathlib import Path

import tomllib

from sbz_completion import handle_completion


def get_version() -> str:
    """Read version from pyproject.toml."""
    try:
        # Try script directory first (direct execution)
        toml_path = Path(__file__).parent / "pyproject.toml"
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            return data["project"]["version"]
        # Try installed package (uv tool)
        # importlib.resources for package metadata
        from importlib.metadata import version as get_pkg_version
        return get_pkg_version("sbz")
    except Exception:
        return "?.?.?"


VERSION = get_version()

DEFAULT_ENV = ["HOME", "USER", "SHELL", "TERM", "LANG", "LC_ALL", "PATH", "PWD"]

# Filesystem paths mounted read-only (must exist on host)
RO_PATHS = ["/usr", "/bin", "/sbin", "/etc", "/lib", "/lib64", "/var"]

# Optional paths mounted read-only if they exist
OPTIONAL_RO = ["/nix", "/boot", "/sys"]


def die(msg: str) -> None:
    print(f"sbz: error: {msg}", file=sys.stderr)
    sys.exit(1)


def exists(path: str) -> bool:
    return Path(path).exists()


def build_mounts(workspace: str, extra_rw: list[str], extra_ro: list[str], aws: bool = False) -> list[str]:
    """Build bwrap mount arguments."""
    args = [
        "--die-with-parent",
        "--hostname", "sbz",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--tmpfs", "/run",
    ]

    # Read-only system paths
    for p in RO_PATHS:
        args += ["--ro-bind", p, p]

    # Resolve resolv.conf symlink into /run (systemd-resolved)
    resolv = Path("/etc/resolv.conf")
    if resolv.is_symlink():
        target = str(resolv.resolve())
        if target.startswith("/run/") and exists(target):
            run_dir = str(Path(target).parent)
            args += ["--ro-bind", run_dir, run_dir]

    # Optional paths
    for p in OPTIONAL_RO:
        if exists(p):
            args += ["--ro-bind", p, p]

    # Home: read-only base
    home = os.environ["HOME"]
    args += ["--ro-bind", home, home]

    # ~/.cache → tmpfs (tool caches, writable, não persiste no host)
    if exists(f"{home}/.cache"):
        args += ["--tmpfs", f"{home}/.cache"]

    # Diretórios sensíveis → tmpfs vazio (protegidos)
    sensitive = [".ssh"] if aws else [".ssh", ".aws"]
    for d in sensitive:
        if exists(f"{home}/{d}"):
            args += ["--tmpfs", f"{home}/{d}"]

    # ~/.aws → read-only do host (quando --aws)
    if aws:
        aws_dir = f"{home}/.aws"
        if exists(aws_dir):
            args += ["--ro-bind", aws_dir, aws_dir]

    # ~/.ssh/known_hosts → read-only do host (evita prompt de host key)
    kh = f"{home}/.ssh/known_hosts"
    if exists(kh):
        args += ["--ro-bind", kh, kh]

    # ~/.pi/agent → read-write (pi settings, sessions, etc)
    pi_agent = f"{home}/.pi/agent"
    if exists(pi_agent):
        args += ["--bind", pi_agent, pi_agent]

    # ~/.local/share writable subdirs (bind — persiste no host)
    for d in ["zoxide", "uv", "opencode"]:
        p = f"{home}/.local/share/{d}"
        if exists(p):
            args += ["--bind", p, p]

    # Workspace: read-write
    args += ["--bind", workspace, workspace]

    # Additional mounts
    for d in extra_rw:
        if not exists(d):
            die(f"directory not found: {d}")
        real = str(Path(d).resolve())
        args += ["--bind", real, real]

    for d in extra_ro:
        if not exists(d):
            die(f"directory not found: {d}")
        real = str(Path(d).resolve())
        args += ["--ro-bind", real, real]

    return args


def build_env(extra_vars: list[str]) -> list[str]:
    """Build --setenv arguments for essential + requested env vars."""
    args = []
    for var in DEFAULT_ENV + extra_vars:
        val = os.environ.get(var)
        if val:
            args += ["--setenv", var, val]
    return args


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    """Parse sbz options and split command from the first non-option arg."""
    # Flags that consume the next arg as their value
    flags_with_value = {"-w", "--workspace", "-rw", "--read-write", "-ro", "--read-only", "-e", "--env"}

    argv = sys.argv[1:]
    options: list[str] = []
    command: list[str] = []
    i = 0

    while i < len(argv):
        arg = argv[i]

        if arg == "--":
            command = argv[i + 1:]
            break

        if arg.startswith("-") and arg not in ("--",):
            options.append(arg)
            # Consume next arg as value for flags that need one
            if arg in flags_with_value:
                i += 1
                if i < len(argv):
                    options.append(argv[i])
        else:
            # First non-option arg starts the command
            command = argv[i:]
            break

        i += 1

    parser = argparse.ArgumentParser(
        prog="sbz",
        description="Sandboxed command execution via bubblewrap",
        usage="%(prog)s [OPTIONS] [--] COMMAND [ARGS...]",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-V", "--version", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--net", dest="network", action="store_true", default=True)
    parser.add_argument("--no-net", dest="network", action="store_false")
    parser.add_argument("--gh", dest="gh", action="store_true", default=True)
    parser.add_argument("--no-gh", dest="gh", action="store_false")
    parser.add_argument("--aws", dest="aws", action="store_true", default=False)
    parser.add_argument("--no-aws", dest="aws", action="store_false")
    parser.add_argument("-w", "--workspace", default=None)
    parser.add_argument("-rw", "--read-write", action="append", default=[])
    parser.add_argument("-ro", "--read-only", action="append", default=[])
    parser.add_argument("-e", "--env", action="append", default=[], metavar="VAR")

    args = parser.parse_args(options)

    if args.help:
        show_help()

    if args.version:
        print(f"sbz v{VERSION}")
        sys.exit(0)

    return args, command


def show_help(exit_code: int = 0) -> None:
    print(f"""usage: sbz [OPTIONS] [--] COMMAND [ARGS...]

Sandboxed command execution via bubblewrap.

options:
  -h, --help             show this help
  -V, --version          show version
  -v, --verbose          show bwrap arguments
  -w, --workspace DIR    workspace directory (default: $PWD)
  -rw, --read-write DIR  mount directory as read-write
  -ro, --read-only DIR   mount directory as read-only
  -e, --env VAR          pass environment variable (can repeat)

flags (default shown):
  --net / --no-net       network access          [default: --net]
  --gh / --no-gh         SSH agent forwarding    [default: --gh]
  --aws / --no-aws       ~/.aws read-only        [default: --no-aws]

examples:
  sbz ls -la                              # sandbox with network
  sbz --no-net curl example.com           # no network
  sbz --no-gh git push                    # block SSH agent
  sbz --aws aws s3 ls                     # access AWS credentials
  sbz -rw /tmp/data python train.py       # extra rw mount
  sbz -e API_KEY -w /proj node app.js     # pass env var
  sbz completion bash                   # print bash completion script

note: `sbz -- CMD` runs CMD literally (use for a binary named `completion`).

environment:
  SBZ_WORKSPACE   default workspace (overrides $PWD)""")
    sys.exit(exit_code)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "completion":
        handle_completion(sys.argv[2:])

    args, command = parse_args()

    if not command:
        show_help(exit_code=1)

    # Resolve workspace
    workspace = args.workspace or os.environ.get("SBZ_WORKSPACE") or os.getcwd()
    if not exists(workspace):
        die(f"workspace not found: {workspace}")
    workspace = str(Path(workspace).resolve())

    # Build bwrap arguments
    bwrap = build_mounts(workspace, args.read_write, args.read_only)

    # Chdir to workspace
    bwrap += ["--chdir", workspace]

    # Network mode
    if args.network:
        # Share host network, isolate other namespaces
        bwrap += ["--unshare-pid", "--unshare-uts", "--unshare-ipc", "--unshare-user"]
    else:
        # Full isolation including network
        bwrap += ["--unshare-all"]

    # Environment
    extra_env = list(args.env)
    if args.gh:
        extra_env.append("SSH_AUTH_SOCK")
    bwrap += build_env(extra_env)

    # --gh: monta o socket do SSH agent como rw
    if args.gh:
        sock = os.environ.get("SSH_AUTH_SOCK", "")
        if sock and exists(sock):
            bwrap += ["--bind", sock, sock]

    # --no-gh: limpa SSH_AUTH_SOCK
    if not args.gh:
        bwrap += ["--setenv", "SSH_AUTH_SOCK", ""]

    # Run
    if args.verbose:
        print(f"sbz: workspace={workspace} net={args.network}", file=sys.stderr)
        print(f"sbz: bwrap {' '.join(bwrap)} {' '.join(command)}", file=sys.stderr)

    os.execvp("bwrap", ["bwrap"] + bwrap + command)


if __name__ == "__main__":
    main()
