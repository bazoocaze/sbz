#!/usr/bin/env python3
"""sbz — Sandboxed command execution via bubblewrap."""

import optparse
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from sbz_completion import handle_completion


def get_version() -> str:
    """Read version from pyproject.toml (dev) or package metadata (installed)."""
    try:
        toml_path = Path(__file__).parent / "pyproject.toml"
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                return tomllib.load(f)["project"]["version"]
        from importlib.metadata import version as get_pkg_version
        return get_pkg_version("sbz")
    except Exception:  # noqa: BLE001
        return "?.?.?"


VERSION = get_version()

DEFAULT_ENV = ["HOME", "USER", "SHELL", "TERM", "LANG", "LC_ALL", "PATH"]

# Filesystem paths mounted read-only (must exist on host)
RO_PATHS = ["/usr", "/bin", "/sbin", "/etc", "/lib", "/lib64", "/var"]

# Optional paths mounted read-only if they exist
OPTIONAL_RO = ["/opt", "/nix", "/boot", "/sys"]

# Always applied, no profile needed
GLOBAL_RW = [".pi/agent", ".local/share/zoxide", ".local/share/uv", ".local/share/opencode"]


@dataclass(frozen=True)
class Cap:
    """A permission: op applied to a resource (path, env var, or network)."""

    op: str
    target: str


def read(target: str) -> Cap:
    return Cap("read", target)


def write(target: str) -> Cap:
    return Cap("write", target)


def deny(target: str) -> Cap:
    return Cap("deny", target)


def agent() -> Cap:
    return Cap("agent", "")


def net() -> Cap:
    return Cap("net", "network")


def nonet() -> Cap:
    return Cap("nonet", "network")


PROTECTIONS = [deny("~/.ssh"), deny("~/.aws")]

PROFILES = {
    "default": [],
    "dev": [read("~/.ssh/known_hosts"), read("~/.m2/settings.xml"), agent()],
    "gh": [read("~/.ssh/known_hosts"), agent()],
    "aws": [read("~/.aws")],
    "docker": [write("/run/docker.sock")],
    "ssh": [read("~/.ssh")],
}


def die(msg: str, code: int = 1) -> None:
    print(f"sbz: error: {msg}", file=sys.stderr)
    sys.exit(code)


def exists(path: str) -> bool:
    return Path(path).exists()


def expand(target: str) -> str:
    """Resolve ~ in a cap target."""
    if target.startswith("~"):
        return os.environ.get("HOME", "") + target[1:]
    return target


def cap_key(cap: Cap) -> str:
    """One entry per resource, so the last cap applied wins."""
    if cap.op in ("net", "nonet"):
        return "net"
    if cap.op == "agent":
        return "agent"
    return f"path:{expand(cap.target)}"


def parse_profiles(argv: list[str]) -> tuple[list[str], list[str]]:
    """Consume leading @profile tokens; the rest is flags and the command."""
    profiles = []
    rest = list(argv)
    while rest and rest[0].startswith("@"):
        for name in rest[0][1:].split(","):
            if name not in PROFILES:
                die(f"unknown profile: {name} (valid: {', '.join(sorted(PROFILES))})")
            profiles.append(name)
        rest.pop(0)
    return profiles, rest


def flag_caps(opts) -> list[Cap]:
    """Flags are shorthand for caps; they override the profile."""
    caps = []
    if opts.no_net:
        caps.append(nonet())
    for d in opts.read:
        caps.append(read(d))
    for d in opts.write:
        caps.append(write(d))
    return caps


def resolve(profiles: list[str], flags: list[Cap]) -> list[Cap]:
    """Baseline protections, then profile grants, then flags (last wins per resource)."""
    caps = {}
    for cap in [net()] + PROTECTIONS:
        caps[cap_key(cap)] = cap
    for name in profiles:
        for cap in PROFILES[name]:
            caps[cap_key(cap)] = cap
    for cap in flags:
        caps[cap_key(cap)] = cap
    return list(caps.values())


def build_args(caps: list[Cap], workspace: str) -> list[str]:
    """Build bwrap arguments from resolved caps."""
    args = [
        "--die-with-parent",
        "--new-session",
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
    home = os.environ.get("HOME")
    if not home:
        die("HOME is not set")
    args += ["--ro-bind", home, home]

    # Workspace: read-write (before writable overrides so it can't re-expose them)
    args += ["--bind", workspace, workspace]

    # ~/.cache → tmpfs (tool caches, writable, não persiste no host)
    if exists(f"{home}/.cache"):
        args += ["--tmpfs", f"{home}/.cache"]

    # Global writable grants
    for d in GLOBAL_RW:
        p = f"{home}/{d}"
        if exists(p):
            args += ["--bind", p, p]

    # Caps in insertion order: protections first, then grants
    for cap in caps:
        if cap.op == "agent":
            sock = os.environ.get("SSH_AUTH_SOCK")
            if sock and exists(sock):
                args += ["--setenv", "SSH_AUTH_SOCK", sock, "--bind", sock, sock]
            continue
        if cap_key(cap) == "net":
            continue
        path = expand(cap.target)
        if not path or not exists(path):
            continue
        if cap.op == "deny":
            if Path(path).is_dir():
                args += ["--tmpfs", path]
            else:
                args += ["--ro-bind", "/dev/null", path]
        elif cap.op == "read":
            args += ["--ro-bind", path, path]
        else:
            args += ["--bind", path, path]

    # Chdir to workspace
    args += ["--chdir", workspace, "--setenv", "PWD", workspace]

    # Network mode
    net_cap = next((c for c in caps if cap_key(c) == "net"), net())
    if net_cap.op == "net":
        # Share host network, isolate other namespaces
        args += ["--unshare-pid", "--unshare-uts", "--unshare-ipc", "--unshare-user"]
    else:
        # Full isolation including network
        args += ["--unshare-all"]

    # Environment
    for var in DEFAULT_ENV:
        val = os.environ.get(var)
        if val:
            args += ["--setenv", var, val]

    return args


def build_parser() -> optparse.OptionParser:
    parser = optparse.OptionParser(
        prog="sbz",
        usage="sbz [@profiles] [OPTIONS] [--] COMMAND [ARGS...]",
        description="Sandboxed command execution via bubblewrap.",
        epilog=(
            "profiles: @default, @dev, @gh, @aws, @docker, @ssh (comma-separated, default @default)\n"
            "flags are shorthand for caps and override the profile.\n"
            "security: @gh/@dev forward your SSH agent; @docker grants root-equivalent host access."
        ),
    )
    parser.version = f"sbz v{VERSION}"
    parser.add_option("-V", "--version", action="version", help="show version")
    parser.add_option("-v", "--verbose", action="store_true", help="show bwrap arguments")
    parser.add_option("--no-net", dest="no_net", action="store_true", help="disable network access")
    parser.add_option("-r", "--read", action="append", default=[], metavar="DIR", help="grant read (ro-bind)")
    parser.add_option("-w", "--write", action="append", default=[], metavar="DIR", help="grant write (bind)")
    parser.add_option("--completion", metavar="SHELL", help="print shell completion script (bash/zsh/fish)")
    parser.disable_interspersed_args()
    return parser


def main() -> None:
    profiles, argv = parse_profiles(sys.argv[1:])
    parser = build_parser()
    opts, command = parser.parse_args(argv)

    if opts.completion:
        handle_completion([opts.completion])
        return

    if not command:
        parser.error("no command given")

    # Resolve workspace
    workspace = os.environ.get("SBZ_WORKSPACE") or os.getcwd()
    if not exists(workspace):
        die(f"workspace not found: {workspace}")
    workspace = str(Path(workspace).resolve())

    flags = flag_caps(opts)
    caps = resolve(profiles, flags)
    bwrap = build_args(caps, workspace)

    # verbose
    if opts.verbose:
        print(f"sbz: profiles={','.join(profiles) or 'default'} workspace={workspace}", file=sys.stderr)
        print(f"sbz: caps {' '.join(f'{c.op}({c.target})' for c in caps)}", file=sys.stderr)
        print(f"sbz: bwrap {' '.join(bwrap)} {' '.join(command)}", file=sys.stderr)

    try:
        os.execvp("bwrap", ["bwrap"] + bwrap + command)
    except FileNotFoundError:
        die("bwrap not found in PATH")


if __name__ == "__main__":
    main()
