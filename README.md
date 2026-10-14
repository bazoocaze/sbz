# sbz

Sandboxed command execution via bubblewrap.

## Install

```bash
uv tool install git+https://github.com/bazoocaze/sbz
```

## Usage

```bash
sbz ls -la                                  # baseline sandbox, with network
sbz @dev mvn compile                        # agent + known_hosts + ~/.m2/settings.xml
sbz @gh git push                            # SSH agent forwarding
sbz @aws aws s3 ls                          # ~/.aws (ro) + SSO/CLI caches (rw)
sbz @docker docker ps                       # Docker socket
sbz @ssh ssh user@host                      # ~/.ssh keys
sbz @dev,aws --no-net env                   # profiles are unioned
sbz @default -r ~/.m2/settings.xml mvn -version  # one-off grant
sbz -w /tmp/data python train.py            # one-off grant
```

Profiles are optional, comma-separated, and must come first (`@default` when omitted).
Flags are shorthand for a single cap and override the profile. Workspace is `$PWD` (or `SBZ_WORKSPACE`).

## Model

Baseline is always applied (system paths ro, home ro, workspace rw, `~/.cache` tmpfs, global rw dirs, network, and `deny` on `~/.ssh`, `~/.aws` and `~/.m2/settings.xml`). Profiles are **grants only** — exceptions to the baseline, never inheritance.

## Profiles

| profile | grants |
|---|---|
| `@default` | – |
| `@dev` | read `~/.ssh/known_hosts`, read `~/.m2/settings.xml`, SSH agent |
| `@gh` | read `~/.ssh/known_hosts`, SSH agent |
| `@aws` | read `~/.aws`, write `~/.aws/sso/cache` and `~/.aws/cli/cache` |
| `@docker` | Docker socket |
| `@ssh` | read `~/.ssh` |

## Options

```
  -h, --help             show this help
  -V, --version          show version
  -v, --verbose          show bwrap arguments
  -r, --read DIR         grant read (ro-bind)
  -w, --write DIR        grant write (bind)
  --no-net               disable network access
  --completion SHELL     print shell completion script (bash/zsh/fish)
```

## Environment

- `SBZ_WORKSPACE` - default workspace (overrides $PWD)

## Security

- `@dev` / `@gh` forward your SSH agent to the sandbox, so sandboxed commands can use your keys.
- `@docker` mounts the Docker socket, granting root-equivalent access to the host.
- `@aws` keeps `~/.aws` read-only but overlays `~/.aws/sso/cache` and `~/.aws/cli/cache` as writable, so SSO token refresh works while `config`/`credentials` stay protected.
- `~/.m2/settings.xml` is denied by default (it can hold repository/server credentials); `@dev` exposes it read-only.

## Completion

```bash
eval "$(sbz --completion bash)"    # bash (~/.bashrc)
eval "$(sbz --completion zsh)"     # zsh (~/.zshrc)
sbz --completion fish | source     # fish (config.fish)
```

Note: `sbz -- CMD` runs `CMD` literally (for commands starting with `-`).

## Development

```bash
./run-tests.sh          # run tests (pytest)
./run-app.sh --version  # run from source
```

## Permissions

`🔎` = read-only (ro-bind), `✅` = writable (bind/tmpfs, network, SSH agent), `⛔` = denied (empty tmpfs / `/dev/null`), `-` = not available.

**Effective** permissions of each run. `baseline` is the run with no profile — the baseline is always applied, and it is identical to `@default`; the other columns add that profile on top. The `flags` column shows flags dedicated to a permission (the generic `-r`/`-w` target any path, so they are not listed).

| permissão | flags | baseline | @dev | @gh | @aws | @docker | @ssh |
|---|---|---|---|---|---|---|---|
| system paths | - | 🔎 | 🔎 | 🔎 | 🔎 | 🔎 | 🔎 |
| home | - | 🔎 | 🔎 | 🔎 | 🔎 | 🔎 | 🔎 |
| workspace | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `~/.cache` | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `~/.pi/agent` | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `~/.local/share/{zoxide,uv,opencode}` | - | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| network | `--no-net` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `~/.ssh` | - | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | 🔎 |
| `~/.ssh/known_hosts` | - | ⛔ | 🔎 | 🔎 | ⛔ | ⛔ | 🔎 |
| `~/.aws` | - | ⛔ | ⛔ | ⛔ | 🔎 | ⛔ | ⛔ |
| `~/.aws/{sso,cli}/cache` | - | ⛔ | ⛔ | ⛔ | ✅ | ⛔ | ⛔ |
| `~/.m2/settings.xml` | - | ⛔ | 🔎 | ⛔ | ⛔ | ⛔ | ⛔ |
| SSH agent | - | - | ✅ | ✅ | - | - | - |
| Docker socket | - | - | - | - | - | ✅ | - |
