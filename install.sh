#!/usr/bin/env bash
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUPPORTED_SHELLS="bash zsh fish"

usage() {
    echo "Uso: ./install.sh --shell <shell|auto|all>"
    echo "  --shell zsh    instala só para zsh"
    echo "  --shell bash   instala só para bash"
    echo "  --shell fish   instala só para fish"
    echo "  --shell auto   detecta o shell atual"
    echo "  --shell all    instala para todos os shells disponíveis"
    exit 1
}

detect_shell() {
    basename "${SHELL:-bash}"
}

install_for_shell() {
    local shell="$1"
    local src rc_file line

    case "$shell" in
        zsh)
            src="$REPO_DIR/zsh/wpptrans.zsh"
            rc_file="$HOME/.zshrc"
            line="source \"$src\""
            ;;
        bash)
            src="$REPO_DIR/bash/wpptrans.sh"
            rc_file="$HOME/.bashrc"
            line="source \"$src\""
            ;;
        fish)
            src="$REPO_DIR/fish/wpptrans.fish"
            rc_file="$HOME/.config/fish/config.fish"
            line="source \"$src\""
            ;;
        *)
            echo "Shell não suportado: $shell" >&2
            return 1
            ;;
    esac

    if [[ ! -f "$src" ]]; then
        echo "[$shell] Arquivo não encontrado: $src — pulando." >&2
        return 1
    fi

    if grep -qF "$src" "$rc_file" 2>/dev/null; then
        echo "[$shell] Já instalado em $rc_file — nada a fazer."
        return 0
    fi

    mkdir -p "$(dirname "$rc_file")"
    touch "$rc_file"

    echo "" >> "$rc_file"
    echo "# wpptrans — transcrição de áudios WhatsApp" >> "$rc_file"
    echo "$line" >> "$rc_file"

    echo "[$shell] Instalado em $rc_file"
    echo "[$shell] Execute: source $rc_file"
}

SHELL_TARGET=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --shell) SHELL_TARGET="${2:-}"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "Argumento desconhecido: $1" >&2; usage ;;
    esac
done

[[ -z "$SHELL_TARGET" ]] && usage

case "$SHELL_TARGET" in
    auto) install_for_shell "$(detect_shell)" ;;
    all)
        for s in $SUPPORTED_SHELLS; do
            install_for_shell "$s" || true
        done
        ;;
    *) install_for_shell "$SHELL_TARGET" ;;
esac
