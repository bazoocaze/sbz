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
sbz -rw /tmp/data python train.py       # extra rw mount
sbz -e API_KEY -w /proj node app.js     # pass env var
```

## Options

```
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
```

## Environment

- `SBZ_WORKSPACE` - default workspace (overrides $PWD)
