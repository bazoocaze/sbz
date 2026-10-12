# TASK: @aws SSO cache write failure

## Scope
Fix `@aws` profile failing on AWS CLI SSO token refresh inside the sandbox.

## Bug

- [x] `@aws` mounted `~/.aws` read-only, so AWS CLI could not persist refreshed SSO
  tokens: `[Errno 30] Read-only file system: ~/.aws/sso/cache/*.json`.
  Worked until the cached token expired, then every command failed.

## Fix

- [x] `PROFILES["aws"]` now overlays `~/.aws/sso/cache` and `~/.aws/cli/cache` as
  writable binds, applied after the `~/.aws` ro-bind. `config`/`credentials` stay
  read-only.
- [x] Test `test_aws_profile_allows_sso_cache_writes` asserts the writable binds
  come after the ro-bind.

## Out of scope
Version bump, tag/release (per AGENTS.md).
