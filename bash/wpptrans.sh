################################################################################
# wpptrans — transcreve áudios de WhatsApp (.ogg/Opus) via whisper.cpp
# Funções disponíveis:
#   wpptrans <arquivo> [modelo]      — transcreve, mantém o arquivo
#   wpptrans_rm <arquivo> [modelo]   — transcreve e remove (só de ~/Downloads/)
#   wpptrans_last [modelo]           — transcreve o .ogg mais recente em ~/Downloads/
#   wpptrans_last_rm [modelo]        — transcreve e remove o .ogg mais recente
################################################################################

_wpptrans_decode_path() {
    local raw="$1"
    raw="${raw#file://}"
    python3 -c "import sys, urllib.parse; print(urllib.parse.unquote(sys.argv[1]))" "$raw"
}

_wpptrans_run() {
    local filepath="$1"
    local model="${2:-small}"
    local model_path="$HOME/.cache/whispercpp/models/ggml-${model}.bin"

    if [[ ! -f "$model_path" ]]; then
        echo "Erro: modelo '$model' não encontrado em $model_path" >&2
        return 1
    fi

    local tmp_wav
    tmp_wav="$(mktemp /tmp/wpptrans_XXXXXX.wav)"

    if ! ffmpeg -y -i "$filepath" -ar 16000 -ac 1 -c:a pcm_s16le "$tmp_wav" -loglevel error; then
        echo "Erro: falha na conversão com ffmpeg" >&2
        rm -f "$tmp_wav"
        return 1
    fi

    echo "--- Transcrição ---"
    whisper-cli -m "$model_path" -f "$tmp_wav" --no-prints -nt 2>/dev/null
    local exit_code=$?
    echo "-------------------"

    rm -f "$tmp_wav"
    return $exit_code
}

wpptrans() {
    if [[ -z "${1:-}" ]]; then
        echo "Uso: wpptrans <arquivo.ogg> [modelo]" >&2
        echo "Modelos: tiny | base | small | medium | large  (padrão: small)" >&2
        return 1
    fi

    local filepath
    filepath="$(_wpptrans_decode_path "$1")"
    local model="${2:-small}"

    if [[ ! -f "$filepath" ]]; then
        echo "Erro: arquivo não encontrado: $filepath" >&2
        return 1
    fi

    _wpptrans_run "$filepath" "$model"
}

wpptrans_rm() {
    if [[ -z "${1:-}" ]]; then
        echo "Uso: wpptrans_rm <arquivo.ogg> [modelo]" >&2
        return 1
    fi

    local filepath
    filepath="$(_wpptrans_decode_path "$1")"
    local model="${2:-small}"

    if [[ ! -f "$filepath" ]]; then
        echo "Erro: arquivo não encontrado: $filepath" >&2
        return 1
    fi

    local downloads_dir
    downloads_dir="$(realpath "$HOME/Downloads")"
    local real_filepath
    real_filepath="$(realpath "$filepath")"

    if [[ "$real_filepath" != "$downloads_dir"/* ]]; then
        echo "Erro: remoção permitida apenas para arquivos em ~/Downloads/" >&2
        echo "Use 'wpptrans' para arquivos fora de ~/Downloads/" >&2
        return 1
    fi

    if _wpptrans_run "$filepath" "$model"; then
        rm -f "$filepath"
        echo "(arquivo removido: $filepath)"
    else
        echo "Transcrição falhou — arquivo mantido." >&2
        return 1
    fi
}

wpptrans_last() {
    local model="${1:-small}"
    local downloads="$HOME/Downloads"

    local latest
    latest="$(ls -t "$downloads"/*.ogg 2>/dev/null | head -1)"

    if [[ -z "$latest" ]]; then
        echo "Nenhum arquivo .ogg encontrado em ~/Downloads/" >&2
        return 1
    fi

    echo "Arquivo: $latest"
    _wpptrans_run "$latest" "$model"
}

wpptrans_last_rm() {
    local model="${1:-small}"
    local downloads="$HOME/Downloads"

    local latest
    latest="$(ls -t "$downloads"/*.ogg 2>/dev/null | head -1)"

    if [[ -z "$latest" ]]; then
        echo "Nenhum arquivo .ogg encontrado em ~/Downloads/" >&2
        return 1
    fi

    echo "Arquivo: $latest"
    if _wpptrans_run "$latest" "$model"; then
        rm -f "$latest"
        echo "(arquivo removido: $latest)"
    else
        echo "Transcrição falhou — arquivo mantido." >&2
        return 1
    fi
}
