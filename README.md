# sbz

Sandboxed command execution via bubblewrap.

## Install

```bash
uv tool install git+https://github.com/bazoocaze/sbz
```

## Usage

```bash
sbz ls -la                              # sandbox with network
sbz --no-net curl example.com           # no network
sbz --no-gh git push                    # block SSH agent
sbz --aws aws s3 ls                     # access AWS credentials
sbz --docker docker ps                  # access Docker socket
sbz -r /tmp/data python train.py        # extra rw mount
sbz -e API_KEY -w /proj node app.js     # pass env var
```

## Options

```
  -h, --help             show this help
  -V, --version          show version
  -v, --verbose          show bwrap arguments
  -w, --workspace DIR    workspace directory (default: $PWD)
  -r, --read-write DIR   mount directory as read-write
  -R, --read-only DIR    mount directory as read-only
  -e, --env VAR          pass environment variable (can repeat)

flags (default shown):
  --net / --no-net       network access          [default: --net]
  --gh / --no-gh         SSH agent forwarding    [default: --gh]
  --aws / --no-aws       ~/.aws read-only        [default: --no-aws]
  --docker / --no-docker Docker socket access    [default: --no-docker]

  --completion SHELL     print completion script (bash/zsh/fish)
```

## Environment

- `SBZ_WORKSPACE` - default workspace (overrides $PWD)

## Security

- `--gh` (default on) forwards your SSH agent to the sandbox, so sandboxed commands can use your keys.
- `--docker` mounts the Docker socket, granting root-equivalent access to the host.

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
