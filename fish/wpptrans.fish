################################################################################
# wpptrans — transcreve áudios de WhatsApp (.ogg/Opus) via whisper.cpp + Gemini
#
#   wpptrans <arquivo> [modo] [modelo]   — transcreve, mantém o arquivo
#   wpptrans_rm <arquivo> [modo] [modelo]— transcreve e remove (só de ~/Downloads/)
#   wpptrans_last [modo] [modelo]        — transcreve o .ogg mais recente
#   wpptrans_last_rm [modo] [modelo]     — transcreve o mais recente e remove
#   wpptrans_batch [N] [modo] [modelo]   — transcreve os N mais recentes (sem N = todos)
#   wpptrans_batch_rm [N] [modo] [modelo]— igual ao batch e remove ao final (só ~/Downloads/)
#
# Modos (IA via Gemini): resume | tarefas | reply | bullet | all (padrão) | raw
# Modelos: tiny | base | small | medium | large | large-v3-turbo (padrão)
#
# A lógica vive em wpptrans.py (na raiz do repo); estas funções são só atalhos.
################################################################################

# Raiz do repo, resolvida no momento do source (fish/ -> repo/).
set -g _WPPTRANS_REPO (path dirname (status dirname))

function _wpptrans_py
    python3 $_WPPTRANS_REPO/wpptrans.py $argv
end

function wpptrans
    _wpptrans_py $argv
end

function wpptrans_rm
    _wpptrans_py --rm $argv
end

function wpptrans_last
    _wpptrans_py --last $argv
end

function wpptrans_last_rm
    _wpptrans_py --last --rm $argv
end

function wpptrans_batch
    # Primeiro argumento numérico = N; ausente = todos.
    if test (count $argv) -ge 1; and string match -qr '^\d+$' -- $argv[1]
        _wpptrans_py --batch $argv[1] $argv[2..-1]
    else
        _wpptrans_py --batch 0 $argv
    end
end

function wpptrans_batch_rm
    if test (count $argv) -ge 1; and string match -qr '^\d+$' -- $argv[1]
        _wpptrans_py --batch $argv[1] --rm $argv[2..-1]
    else
        _wpptrans_py --batch 0 --rm $argv
    end
end
