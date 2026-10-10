"""Completion scripts for sbz (bash/zsh/fish)."""

import sys

SHELLS = ("bash", "zsh", "fish")

BASH_COMPLETION = r"""# sbz bash completion — add to ~/.bashrc: eval "$(sbz --completion bash)"
_sbz() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    if [[ "$cur" == @* ]]; then
        COMPREPLY=( $(compgen -W "@default @dev @gh @aws @docker @ssh" -- "$cur") )
        return 0
    fi

    case "$prev" in
        -r|--read|-w|--write)
            COMPREPLY=( $(compgen -d -- "$cur") )
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

    COMPREPLY=( $(compgen -W "-h --help -V --version -v --verbose --no-net -r --read -w --write --completion" -- "$cur") )
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
        '--no-net[no network access]' \
        '(-r --read)'{-r,--read}'[grant read]:dir:_files -/' \
        '(-w --write)'{-w,--write}'[grant write]:dir:_files -/' \
        '--completion[print shell completion script]:shell:(bash zsh fish)' \
        '1:profile:("@default" "@dev" "@gh" "@aws" "@docker" "@ssh")' \
        '*::command:_normal'
}
compdef _sbz sbz
"""

FISH_COMPLETION = r"""# sbz fish completion — add to ~/.config/fish/config.fish: sbz --completion fish | source
complete -c sbz -f
complete -c sbz -s h -l help -d 'show help'
complete -c sbz -s V -l version -d 'show version'
complete -c sbz -s v -l verbose -d 'show bwrap arguments'
complete -c sbz -l no-net -d 'no network access'
complete -c sbz -s r -l read -r -a '(__fish_print_directories)' -d 'grant read'
complete -c sbz -s w -l write -r -a '(__fish_print_directories)' -d 'grant write'
complete -c sbz -l completion -x -a 'bash zsh fish' -d 'print shell completion script'
complete -c sbz -f -a '@default @dev @gh @aws @docker @ssh' -d 'profile'
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
