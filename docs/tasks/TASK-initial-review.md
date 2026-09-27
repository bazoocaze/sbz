# TASK: Initial project review findings

## Scope
Review of `sbz` (bubblewrap wrapper). Findings below; fixes tracked in this task.

## Bugs

- [x] `--aws` is a no-op: `main()` called `build_mounts(workspace, read_write, read_only)` without `aws=args.aws` (sbz.py:262), so `~/.aws` was always an empty tmpfs.
- [x] `requires-python = ">=3.10"` but `import tomllib` needs 3.11+ (sbz.py:9). Import failed on 3.10.
- [x] `-w ~` breaks sandbox: sensitive `.ssh`/`.aws` tmpfs mounts (sbz.py:88) were added before `--bind workspace` (sbz.py:116), so a home workspace re-exposed the real dirs.
- [x] `/lib64` in `RO_PATHS` (sbz.py:36) is unconditional; missing dir made bwrap fail. Now guarded with `exists()`.

## Robustness / design

- [ ] Manual parser (sbz.py:144) does not handle combined short flags (`-vw dir`), attached `-eVAR`, or `sbz -v completion ...`. Deferred.
- [ ] `handle_completion` lacks explicit `return`/`sys.exit` at caller (sbz.py:247).
- [ ] Inconsistent exit codes (manual help 0/1 vs argparse 2).

## Packaging / repo

- [x] `uv.lock` stale (0.0.2) vs pyproject 0.0.7.
- [x] `.venv/` not in `.gitignore`; local venv is stale (0.0.2).
- [ ] `pyproject.toml` missing readme/license/authors/urls/classifiers. Deferred.

## Security defaults

- [ ] `--gh` enabled by default forwards the SSH agent. Deferred (document only).
- [ ] `--docker` mounts the Docker socket (trivial escape); document risk. Deferred.

## Tests (minimal, non-exhaustive)

- [x] Unit tests for `build_mounts` / `build_env` only, via pytest.

## Out of scope
Version bump, tag/release (per AGENTS.md).
