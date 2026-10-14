# TASK: baseline formalization + ~/.m2/settings.xml deny

## Scope
Give the always-applied baseline a single home in the code, and protect
`~/.m2/settings.xml` by default.

## Changes

- [x] Added `baseline(workspace)` (sbz.py) as the single source of the built-in
  rules: `RO_PATHS`, resolv dir, `OPTIONAL_RO`, home ro, workspace rw,
  `~/.cache` tmpfs, `GLOBAL_RW`, network and `PROTECTIONS`.
- [x] `resolve()` now seeds from `baseline()`; `build_args()` no longer hardcodes
  the base mounts — it renders them through the generic cap loop.
- [x] Added `tmpfs()` cap (op `tmpfs`) for `~/.cache`.
- [x] `PROTECTIONS` also denies `~/.m2/settings.xml`; `PROFILES["dev"]` re-grants
  `read("~/.m2/settings.xml")`. Same `cap_key`, so the profile overrides the
  deny: settings.xml is blocked in every profile except `@dev`.
- [x] README permissions table rewritten as **effective** permissions with a
  `baseline` column. The `@default` column was dropped: it grants nothing, so it
  equals the baseline. Documented the m2 deny under Security.
- [x] Tests: `test_m2_settings_denied_by_default`, `test_dev_grants_m2_settings`,
  `test_gh_denies_m2_settings`.

## Out of scope
Version bump, tag/release (per AGENTS.md).
