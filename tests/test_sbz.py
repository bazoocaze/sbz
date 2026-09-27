"""Minimal unit tests for sbz mount and env builders."""

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


def test_aws_flag_mounts_aws_read_only(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".aws", ".ssh")
    monkeypatch.setenv("HOME", str(home))
    mounts = sbz.build_mounts(str(tmp_path), [], [], aws=True)
    aws = f"{home}/.aws"
    assert has(mounts, "--ro-bind", aws, aws)
    assert not has(mounts, "--tmpfs", aws)


def test_no_aws_hides_aws_dir(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".aws", ".ssh")
    monkeypatch.setenv("HOME", str(home))
    mounts = sbz.build_mounts(str(tmp_path), [], [], aws=False)
    aws = f"{home}/.aws"
    assert has(mounts, "--tmpfs", aws)
    assert not has(mounts, "--ro-bind", aws, aws)


def test_ssh_always_protected(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".ssh")
    monkeypatch.setenv("HOME", str(home))
    for aws in (True, False):
        mounts = sbz.build_mounts(str(tmp_path), [], [], aws=aws)
        assert has(mounts, "--tmpfs", f"{home}/.ssh")


def test_workspace_bind_precedes_protections(tmp_path, monkeypatch):
    home = make_home(tmp_path, ".ssh")
    monkeypatch.setenv("HOME", str(home))
    mounts = sbz.build_mounts(str(home), [], [], aws=False)
    ws = index_of(mounts, "--bind", str(home), str(home))
    ssh = index_of(mounts, "--tmpfs", f"{home}/.ssh")
    assert 0 <= ws < ssh


def test_extra_rw_missing_dies(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit):
        sbz.build_mounts(str(tmp_path), ["/nonexistent-sbz-xyz"], [], aws=False)


def test_extra_ro_existing_ro_binds(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    data = tmp_path / "data"
    data.mkdir()
    mounts = sbz.build_mounts(str(tmp_path), [], [str(data)], aws=False)
    assert has(mounts, "--ro-bind", str(data), str(data))


def test_build_env_passes_only_nonempty(monkeypatch):
    monkeypatch.setenv("SBZ_TEST_SET", "value")
    monkeypatch.delenv("SBZ_TEST_UNSET", raising=False)
    env = sbz.build_env(["SBZ_TEST_SET", "SBZ_TEST_UNSET"])
    assert has(env, "--setenv", "SBZ_TEST_SET", "value")
    assert "SBZ_TEST_UNSET" not in env


def parse(argv):
    return sbz.build_parser().parse_args(argv)


def test_parser_stops_at_first_positional():
    opts, command = parse(["ls", "-la"])
    assert command == ["ls", "-la"]
    assert not opts.verbose


def test_parser_options_before_command():
    opts, command = parse(["-v", "-w", "/tmp", "ls", "-la"])
    assert opts.verbose and opts.workspace == "/tmp"
    assert command == ["ls", "-la"]


def test_parser_bundled_and_attached_values():
    opts, command = parse(["-vw", "/tmp", "true"])
    assert opts.verbose and opts.workspace == "/tmp"
    assert command == ["true"]


def test_parser_double_dash_literal():
    _, command = parse(["--", "-la"])
    assert command == ["-la"]


def test_parser_flag_after_command_goes_to_command():
    opts, command = parse(["ls", "--no-net"])
    assert command == ["ls", "--no-net"]
    assert opts.network is True


def test_parser_read_write_and_read_only():
    opts, _ = parse(["-r", "/a", "-R", "/b", "true"])
    assert opts.read_write == ["/a"] and opts.read_only == ["/b"]


def test_parser_completion_option():
    opts, command = parse(["--completion", "bash"])
    assert opts.completion == "bash" and command == []
