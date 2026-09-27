"""Completion scripts for sbz (bash/zsh/fish)."""

import sys

SHELLS = ("bash", "zsh", "fish")

BASH_COMPLETION = r"""# sbz bash completion — add to ~/.bashrc: eval "$(sbz --completion bash)"
_sbz() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    case "$prev" in
        -w|--workspace|-r|--read-write|-R|--read-only)
            COMPREPLY=( $(compgen -d -- "$cur") )
            return 0
            ;;
        -e|--env)
            COMPREPLY=( $(compgen -v -- "$cur") )
            return 0
            ;;
        --completion)
            COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") )
            return 0
            ;;
    esac

    local w
    for w in "${COMP_WORDS[@]:1:COMP_CWORD-1}"; do
        if [[ "$w" == "--" ]]; then
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
        fi
    done

    COMPREPLY=( $(compgen -W "-h --help -V --version -v --verbose --net --no-net --gh --no-gh --aws --no-aws --docker --no-docker -w --workspace -r --read-write -R --read-only -e --env --completion" -- "$cur") )
}
complete -F _sbz sbz
"""

ZSH_COMPLETION = r"""#compdef sbz
# sbz zsh completion — add to ~/.zshrc: eval "$(sbz --completion zsh)"
_sbz() {
    _arguments -C \
        '(-h --help)'{-h,--help}'[show help]' \
        '(-V --version)'{-V,--version}'[show version]' \
        '(-v --verbose)'{-v,--verbose}'[show bwrap arguments]' \
        '--net[network access]' \
        '--no-net[no network access]' \
        '--gh[SSH agent forwarding]' \
        '--no-gh[block SSH agent]' \
        '--aws[~/.aws read-only]' \
        '--no-aws[hide ~/.aws]' \
        '--docker[Docker socket access]' \
        '--no-docker[block Docker socket]' \
        '(-w --workspace)'{-w,--workspace}'[workspace directory]:dir:_files -/' \
        '(-r --read-write)'{-r,--read-write}'[mount directory as read-write]:dir:_files -/' \
        '(-R --read-only)'{-R,--read-only}'[mount directory as read-only]:dir:_files -/' \
        '(-e --env)'{-e,--env}'[pass environment variable]:var:' \
        '--completion[print shell completion script]:shell:(bash zsh fish)' \
        '*::command:_normal'
}
compdef _sbz sbz
"""

FISH_COMPLETION = r"""# sbz fish completion — add to ~/.config/fish/config.fish: sbz --completion fish | source
complete -c sbz -f
complete -c sbz -s h -l help -d 'show help'
complete -c sbz -s V -l version -d 'show version'
complete -c sbz -s v -l verbose -d 'show bwrap arguments'
complete -c sbz -l net -d 'network access'
complete -c sbz -l no-net -d 'no network access'
complete -c sbz -l gh -d 'SSH agent forwarding'
complete -c sbz -l no-gh -d 'block SSH agent'
complete -c sbz -l aws -d '~/.aws read-only'
complete -c sbz -l no-aws -d 'hide ~/.aws'
complete -c sbz -l docker -d 'Docker socket access'
complete -c sbz -l no-docker -d 'block Docker socket'
complete -c sbz -s w -l workspace -r -a '(__fish_print_directories)' -d 'workspace directory'
complete -c sbz -s r -l read-write -r -a '(__fish_print_directories)' -d 'mount directory as read-write'
complete -c sbz -s R -l read-only -r -a '(__fish_print_directories)' -d 'mount directory as read-only'
complete -c sbz -s e -l env -x -d 'pass environment variable'
complete -c sbz -l completion -x -a 'bash zsh fish' -d 'print shell completion script'
"""

COMPLETION_USAGE = """usage: sbz --completion {bash|zsh|fish}

Generate shell completion script (print to stdout).

examples:
  eval "$(sbz --completion bash)"    # bash (~/.bashrc)
  eval "$(sbz --completion zsh)"     # zsh (~/.zshrc)
  sbz --completion fish | source     # fish (config.fish)"""


def handle_completion(args: list[str]) -> None:
    """Print completion script and exit. `args` is argv after 'completion'."""
    if not args or args[0] in ("-h", "--help"):
        print(COMPLETION_USAGE)
        sys.exit(0)
    if len(args) == 1 and args[0] in SHELLS:
        if args[0] == "bash":
            print(BASH_COMPLETION, end="")
        elif args[0] == "zsh":
            print(ZSH_COMPLETION, end="")
        else:
            print(FISH_COMPLETION, end="")
        sys.exit(0)
    print(f"sbz: error: usage: sbz --completion {{{'|'.join(SHELLS)}}}", file=sys.stderr)
    sys.exit(1)
