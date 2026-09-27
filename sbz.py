#!/usr/bin/env python3
"""sbz — Sandboxed command execution via bubblewrap."""

import optparse
import os
import sys
import tomllib
from pathlib import Path

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
    except Exception:  # noqa: BLE001
        return "?.?.?"


VERSION = get_version()

DEFAULT_ENV = ["HOME", "USER", "SHELL", "TERM", "LANG", "LC_ALL", "PATH", "PWD"]

# Filesystem paths mounted read-only (must exist on host)
RO_PATHS = ["/usr", "/bin", "/sbin", "/etc", "/lib", "/lib64", "/var"]

# Optional paths mounted read-only if they exist
OPTIONAL_RO = ["/opt", "/nix", "/boot", "/sys"]


def die(msg: str, code: int = 1) -> None:
    print(f"sbz: error: {msg}", file=sys.stderr)
    sys.exit(code)


def exists(path: str) -> bool:
    return Path(path).exists()


def build_mounts(workspace: str, extra_rw: list[str], extra_ro: list[str], aws: bool = False) -> list[str]:
    """Build bwrap mount arguments."""
    args = [
        "--die-with-parent",
        "--hostname", "sandbox",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--tmpfs", "/run",
    ]

    # Read-only system paths
    for p in RO_PATHS:
        if exists(p):
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

    # Workspace: read-write (before writable overrides so it can't re-expose them)
    args += ["--bind", workspace, workspace]

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


def build_parser() -> optparse.OptionParser:
    parser = optparse.OptionParser(
        prog="sbz",
        usage="sbz [OPTIONS] [--] COMMAND [ARGS...]",
        description="Sandboxed command execution via bubblewrap.",
        epilog=(
            "security: --gh forwards your SSH agent; "
            "--docker grants root-equivalent host access."
        ),
    )
    parser.version = f"sbz v{VERSION}"
    parser.add_option("-V", "--version", action="version", help="show version")
    parser.add_option("-v", "--verbose", action="store_true", help="show bwrap arguments")
    parser.add_option("--net", dest="network", action="store_true", default=True, help="network access [default]")
    parser.add_option("--no-net", dest="network", action="store_false", help="disable network access")
    parser.add_option("--gh", dest="gh", action="store_true", default=True, help="SSH agent forwarding [default]")
    parser.add_option("--no-gh", dest="gh", action="store_false", help="block SSH agent")
    parser.add_option("--aws", dest="aws", action="store_true", default=False, help="~/.aws read-only")
    parser.add_option("--no-aws", dest="aws", action="store_false", help="hide ~/.aws [default]")
    parser.add_option("--docker", dest="docker", action="store_true", default=False, help="Docker socket access")
    parser.add_option("--no-docker", dest="docker", action="store_false", help="block Docker socket [default]")
    parser.add_option("-w", "--workspace", metavar="DIR", help="workspace directory (default: $PWD)")
    parser.add_option("-r", "--read-write", action="append", dest="read_write", default=[], metavar="DIR", help="mount directory as read-write")
    parser.add_option("-R", "--read-only", action="append", dest="read_only", default=[], metavar="DIR", help="mount directory as read-only")
    parser.add_option("-e", "--env", action="append", default=[], metavar="VAR", help="pass environment variable (repeatable)")
    parser.add_option("--completion", metavar="SHELL", help="print shell completion script (bash/zsh/fish)")
    parser.disable_interspersed_args()
    return parser


def main() -> None:
    parser = build_parser()
    opts, command = parser.parse_args(sys.argv[1:])

    if opts.completion:
        handle_completion([opts.completion])
        return

    if not command:
        parser.error("no command given")

    # Resolve workspace
    workspace = opts.workspace or os.environ.get("SBZ_WORKSPACE") or os.getcwd()
    if not exists(workspace):
        die(f"workspace not found: {workspace}")
    workspace = str(Path(workspace).resolve())

    # Build bwrap arguments
    bwrap = build_mounts(workspace, opts.read_write, opts.read_only, aws=opts.aws)

    # Chdir to workspace
    bwrap += ["--chdir", workspace]

    # Network mode
    if opts.network:
        # Share host network, isolate other namespaces
        bwrap += ["--unshare-pid", "--unshare-uts", "--unshare-ipc", "--unshare-user"]
    else:
        # Full isolation including network
        bwrap += ["--unshare-all"]

    # Environment
    extra_env = list(opts.env)
    if opts.gh:
        extra_env.append("SSH_AUTH_SOCK")
    bwrap += build_env(extra_env)

    # --gh: monta o socket do SSH agent como rw
    if opts.gh:
        sock = os.environ.get("SSH_AUTH_SOCK", "")
        if sock and exists(sock):
            bwrap += ["--bind", sock, sock]

    # --no-gh: limpa SSH_AUTH_SOCK
    if not opts.gh:
        bwrap += ["--setenv", "SSH_AUTH_SOCK", ""]

    # --docker: monta o socket no path real e aponta DOCKER_HOST
    docker_sock = "/run/docker.sock"
    if opts.docker and exists(docker_sock):
        bwrap += ["--bind", docker_sock, docker_sock]
        bwrap += ["--setenv", "DOCKER_HOST", "unix:///run/docker.sock"]

    # verbose
    if opts.verbose:
        print(f"sbz: workspace={workspace} net={opts.network} docker={opts.docker}", file=sys.stderr)
        print(f"sbz: bwrap {' '.join(bwrap)} {' '.join(command)}", file=sys.stderr)

    os.execvp("bwrap", ["bwrap"] + bwrap + command)


if __name__ == "__main__":
    main()
