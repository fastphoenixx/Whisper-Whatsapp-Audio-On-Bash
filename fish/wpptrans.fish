################################################################################
# wpptrans — transcreve áudios de WhatsApp (.ogg/Opus) via whisper.cpp
# Funções disponíveis:
#   wpptrans <arquivo> [modelo]      — transcreve, mantém o arquivo
#   wpptrans_rm <arquivo> [modelo]   — transcreve e remove (só de ~/Downloads/)
#   wpptrans_last [modelo]           — transcreve o .ogg mais recente em ~/Downloads/
#   wpptrans_last_rm [modelo]        — transcreve e remove o .ogg mais recente
################################################################################

function _wpptrans_decode_path
    set -l raw $argv[1]
    set raw (string replace -r '^file://' '' $raw)
    python3 -c "import sys, urllib.parse; print(urllib.parse.unquote(sys.argv[1]))" $raw
end

function _wpptrans_run
    set -l filepath $argv[1]
    set -l model (if test (count $argv) -ge 2; echo $argv[2]; else; echo small; end)
    set -l model_path $HOME/.cache/whispercpp/models/ggml-$model.bin

    if not test -f $model_path
        echo "Erro: modelo '$model' não encontrado em $model_path" >&2
        return 1
    end

    set -l tmp_wav (mktemp /tmp/wpptrans_XXXXXX.wav)

    if not ffmpeg -y -i $filepath -ar 16000 -ac 1 -c:a pcm_s16le $tmp_wav -loglevel error
        echo "Erro: falha na conversão com ffmpeg" >&2
        rm -f $tmp_wav
        return 1
    end

    echo "--- Transcrição ---"
    whisper-cli -m $model_path -f $tmp_wav --no-prints -nt 2>/dev/null
    set -l exit_code $status
    echo "-------------------"

    rm -f $tmp_wav
    return $exit_code
end

function wpptrans
    if test (count $argv) -eq 0
        echo "Uso: wpptrans <arquivo.ogg> [modelo]" >&2
        echo "Modelos: tiny | base | small | medium | large  (padrão: small)" >&2
        return 1
    end

    set -l filepath (_wpptrans_decode_path $argv[1])
    set -l model (if test (count $argv) -ge 2; echo $argv[2]; else; echo small; end)

    if not test -f $filepath
        echo "Erro: arquivo não encontrado: $filepath" >&2
        return 1
    end

    _wpptrans_run $filepath $model
end

function wpptrans_rm
    if test (count $argv) -eq 0
        echo "Uso: wpptrans_rm <arquivo.ogg> [modelo]" >&2
        return 1
    end

    set -l filepath (_wpptrans_decode_path $argv[1])
    set -l model (if test (count $argv) -ge 2; echo $argv[2]; else; echo small; end)

    if not test -f $filepath
        echo "Erro: arquivo não encontrado: $filepath" >&2
        return 1
    end

    set -l downloads_dir (realpath $HOME/Downloads)
    set -l real_filepath (realpath $filepath)

    if not string match -q "$downloads_dir/*" $real_filepath
        echo "Erro: remoção permitida apenas para arquivos em ~/Downloads/" >&2
        echo "Use 'wpptrans' para arquivos fora de ~/Downloads/" >&2
        return 1
    end

    if _wpptrans_run $filepath $model
        rm -f $filepath
        echo "(arquivo removido: $filepath)"
    else
        echo "Transcrição falhou — arquivo mantido." >&2
        return 1
    end
end

function wpptrans_last
    set -l model (if test (count $argv) -ge 1; echo $argv[1]; else; echo small; end)
    set -l downloads $HOME/Downloads

    set -l latest (ls -t $downloads/*.ogg 2>/dev/null | head -1)

    if test -z "$latest"
        echo "Nenhum arquivo .ogg encontrado em ~/Downloads/" >&2
        return 1
    end

    echo "Arquivo: $latest"
    _wpptrans_run $latest $model
end

function wpptrans_last_rm
    set -l model (if test (count $argv) -ge 1; echo $argv[1]; else; echo small; end)
    set -l downloads $HOME/Downloads

    set -l latest (ls -t $downloads/*.ogg 2>/dev/null | head -1)

    if test -z "$latest"
        echo "Nenhum arquivo .ogg encontrado em ~/Downloads/" >&2
        return 1
    end

    echo "Arquivo: $latest"
    if _wpptrans_run $latest $model
        rm -f $latest
        echo "(arquivo removido: $latest)"
    else
        echo "Transcrição falhou — arquivo mantido." >&2
        return 1
    end
end
