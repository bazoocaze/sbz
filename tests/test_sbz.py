"""Minimal unit tests for sbz cap resolution and bwrap arg builder."""

import pytest

import sbz


def has(seq: list[str], *sub: str) -> bool:
    return index_of(seq, *sub) >= 0


def index_of(seq: list[str], *sub: str) -> int:
    n = len(sub)
    for i in range(len(seq) - n + 1):
        if seq[i : i + n] == list(sub):
            return i
    return -1


def make_home(tmp_path, *subdirs):
    home = tmp_path / "home"
    home.mkdir()
    for d in subdirs:
        (home / d).mkdir(parents=True)
    return home


def build(profiles, flags=(), workspace=None, tmp_path=None):
    caps = sbz.resolve(profiles, list(flags))
    return sbz.build_args(caps, str(workspace or tmp_path))


def test_default_is_baseline_only(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".aws", ".ssh")
    monkeypatch.setenv("HOME", str(home))
    mounts = build([], tmp_path=tmp_path)
    assert has(mounts, "--tmpfs", f"{home}/.aws")
    assert has(mounts, "--tmpfs", f"{home}/.ssh")
    assert has(mounts, "--unshare-pid")


def test_aws_profile_grants_aws(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".aws", ".ssh")
    monkeypatch.setenv("HOME", str(home))
    mounts = build(["aws"], tmp_path=tmp_path)
    assert has(mounts, "--ro-bind", f"{home}/.aws", f"{home}/.aws")
    assert not has(mounts, "--tmpfs", f"{home}/.aws")


def test_aws_profile_allows_sso_cache_writes(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".aws/sso/cache", ".aws/cli/cache", ".ssh")
    monkeypatch.setenv("HOME", str(home))
    mounts = build(["aws"], tmp_path=tmp_path)
    aws = index_of(mounts, "--ro-bind", f"{home}/.aws", f"{home}/.aws")
    sso = index_of(mounts, "--bind", f"{home}/.aws/sso/cache", f"{home}/.aws/sso/cache")
    cli = index_of(mounts, "--bind", f"{home}/.aws/cli/cache", f"{home}/.aws/cli/cache")
    # Writable caches must be mounted after the read-only ~/.aws to override it
    assert 0 <= aws < sso and 0 <= aws < cli


def test_ssh_profile_grants_keys(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".ssh", ".aws")
    monkeypatch.setenv("HOME", str(home))
    mounts = build(["ssh"], tmp_path=tmp_path)
    assert has(mounts, "--ro-bind", f"{home}/.ssh", f"{home}/.ssh")
    assert not has(mounts, "--tmpfs", f"{home}/.ssh")
    assert has(mounts, "--tmpfs", f"{home}/.aws")


def test_new_session_is_set(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(make_home(tmp_path)))
    assert "--new-session" in build([], tmp_path=tmp_path)


def test_gh_profile_grants_agent(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".ssh")
    (home / ".ssh" / "known_hosts").write_text("")
    sock = tmp_path / "agent.sock"
    sock.write_text("")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SSH_AUTH_SOCK", str(sock))
    mounts = build(["gh"], tmp_path=tmp_path)
    assert has(mounts, "--setenv", "SSH_AUTH_SOCK", str(sock))
    assert has(mounts, "--bind", str(sock), str(sock))
    assert has(mounts, "--ro-bind", f"{home}/.ssh/known_hosts", f"{home}/.ssh/known_hosts")
    assert not has(mounts, "--ro-bind", f"{home}/.m2/settings.xml", f"{home}/.m2/settings.xml")


def test_dev_grants_agent_and_m2_settings(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".m2", ".ssh")
    (home / ".m2" / "settings.xml").write_text("")
    monkeypatch.setenv("HOME", str(home))
    caps = sbz.resolve(["dev"], [])
    assert sbz.agent() in caps
    args = sbz.build_args(caps, str(tmp_path))
    assert has(args, "--ro-bind", f"{home}/.m2/settings.xml", f"{home}/.m2/settings.xml")


def test_docker_profile_grants_socket(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(make_home(tmp_path)))
    args = build(["docker"], tmp_path=tmp_path)
    assert has(args, "--bind", "/run/docker.sock", "/run/docker.sock")


def test_profiles_do_not_inherit(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".aws", ".ssh")
    monkeypatch.setenv("HOME", str(home))
    caps = sbz.resolve(["aws"], [])
    assert sbz.read("~/.aws") in caps
    assert sbz.agent() not in caps
    assert sbz.read("~/.ssh/known_hosts") not in caps


def test_flag_overrides_profile(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".aws")
    monkeypatch.setenv("HOME", str(home))
    opts = sbz.build_parser().parse_args(["-r", f"{home}/.aws", "true"])[0]
    mounts = build(["default"], sbz.flag_caps(opts), tmp_path=tmp_path)
    assert has(mounts, "--ro-bind", f"{home}/.aws", f"{home}/.aws")
    assert not has(mounts, "--tmpfs", f"{home}/.aws")


def test_workspace_bind_precedes_protections(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".ssh")
    monkeypatch.setenv("HOME", str(home))
    mounts = build([], workspace=home, tmp_path=tmp_path)
    ws = index_of(mounts, "--bind", str(home), str(home))
    ssh = index_of(mounts, "--tmpfs", f"{home}/.ssh")
    assert 0 <= ws < ssh


def test_no_net_uses_full_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(make_home(tmp_path)))
    opts = sbz.build_parser().parse_args(["--no-net", "true"])[0]
    mounts = build([], sbz.flag_caps(opts), tmp_path=tmp_path)
    assert has(mounts, "--unshare-all")


def test_deny_file_uses_dev_null(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".m2")
    (home / ".m2" / "settings.xml").write_text("")
    monkeypatch.setenv("HOME", str(home))
    args = build(["default"], [sbz.deny(f"{home}/.m2/settings.xml")], tmp_path=tmp_path)
    assert has(args, "--ro-bind", "/dev/null", f"{home}/.m2/settings.xml")


def test_missing_path_is_skipped_silently(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(make_home(tmp_path)))
    args = build([], [sbz.write("/tmp/sbz-nope")], tmp_path=tmp_path)
    assert not has(args, "/tmp/sbz-nope")


def parse(argv):
    profiles, rest = sbz.parse_profiles(argv)
    return profiles, sbz.build_parser().parse_args(rest)


def test_parse_profiles_default():
    profiles, (_, command) = parse(["ls", "-la"])
    assert profiles == [] and command == ["ls", "-la"]


def test_parse_profiles_comma_list():
    profiles, (opts, command) = parse(["@dev,aws", "-v", "true"])
    assert profiles == ["dev", "aws"]
    assert opts.verbose and command == ["true"]


def test_parse_profiles_unknown_dies():
    with pytest.raises(SystemExit):
        parse(["@nope", "true"])


def test_profiles_only_at_start():
    profiles, (_, command) = parse(["true", "@dev"])
    assert profiles == [] and command == ["true", "@dev"]


def test_parser_stops_at_first_positional():
    _, (opts, command) = parse(["ls", "-la"])
    assert command == ["ls", "-la"]
    assert not opts.no_net


def test_parser_repeatable_flags():
    _, (opts, _) = parse(["-r", "/a", "-w", "/b", "true"])
    assert opts.read == ["/a"] and opts.write == ["/b"]


def test_parser_double_dash_literal():
    _, (_, command) = parse(["--", "-la"])
    assert command == ["-la"]


def test_parser_completion_option():
    _, (opts, command) = parse(["--completion", "bash"])
    assert opts.completion == "bash" and command == []
