# Whisper WhatsApp Audio (wpptrans)

Transcreve áudios do WhatsApp (geralmente `.ogg`/Opus) usando **whisper.cpp** (`whisper-cli`) + **ffmpeg**, renderiza bonito no terminal e — opcionalmente — gera **resumo, tarefas, resposta provável e pontos-chave** via **Gemini**.

O foco aqui é fluxo rápido:
- colou/arrastou o arquivo → transcreveu no terminal, em parágrafo legível e com painel
- transcrição em **batch** (vários áudios de uma vez)
- **análise por IA** (Gemini) logo após a transcrição
- opção de apagar o áudio original (com guarda)

> A versão turbinada (painel, batch, IA) vive em `wpptrans.py` e é exposta pelas funções **fish**. As variantes `bash`/`zsh` ainda existem com o comportamento básico antigo.

---

## Requisitos

### Dependências
- `ffmpeg` (inclui `ffprobe`)
- `whisper-cli` (whisper.cpp; recomendado o build CUDA)
- `python3` (núcleo `wpptrans.py`)
- `gemini` CLI autenticado — opcional, só para a camada de IA (`gemini --skip-trust -p ...`)
- `bat` — opcional, renderiza o markdown da análise com cor

### Modelo (ggml)
O modelo precisa estar em:
`~/.cache/whispercpp/models/ggml-<model>.bin`

Exemplo (small):
```bash
mkdir -p ~/.cache/whispercpp/models
curl -L -o ~/.cache/whispercpp/models/ggml-small.bin   https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
```

---

## Instalação (recomendada)

Clone o repo e rode o instalador:

```bash
git clone https://github.com/fastphoenixx/Whisper-Whatsapp-Audio-On-Bash.git
cd Whisper-Whatsapp-Audio-On-Bash
chmod +x install.sh
./install.sh --shell auto
```

### Instalar para um shell específico
```bash
./install.sh --shell fish
./install.sh --shell zsh
./install.sh --shell bash
```

### Instalar para todos
```bash
./install.sh --shell all
```

### Não baixar modelo automaticamente
```bash
./install.sh --download-model none
```

> O instalador é idempotente: pode rodar de novo sem bagunçar seu `.bashrc`/`.zshrc`.

---

## Uso

### Transcrever um arquivo (não apaga o original)
```bash
wpptrans "/home/user/Downloads/WhatsApp Audio 2026-02-13 at 12.00.58 PM.ogg"
```

Também funciona colando do navegador (URL `file://` com `%20`):
```bash
wpptrans "file:///home/user/Downloads/WhatsApp%20Audio%202026-02-13%20at%2012.00.58%20PM.ogg"
```

Por padrão a transcrição já vem seguida da análise completa do Gemini
(resumo + tarefas + resposta provável + pontos-chave).

### Modos de IA (qual análise mostrar)

Passe uma palavra de **modo** em qualquer posição:

| Modo | Mostra |
|---|---|
| `resume` / `resumo` | só o resumo |
| `tarefas` / `tasks` | só a checklist de tarefas |
| `reply` / `resposta` | só o rascunho de resposta |
| `bullet` / `pontos` | só os pontos-chave |
| `all` (padrão) | tudo |
| `raw` / `texto` | só a transcrição, sem IA |

```bash
wpptrans "/home/user/Downloads/audio.ogg" resume      # transcrição + só resumo
wpptrans "/home/user/Downloads/audio.ogg" raw         # só transcrição, sem Gemini
```

### Batch (vários áudios)
```bash
wpptrans_batch          # transcreve todos os .ogg de ~/Downloads
wpptrans_batch 6        # só os 6 mais recentes
wpptrans_batch 4 resume # 4 mais recentes, mostrando só o resumo
```

### Modelos
```bash
wpptrans "/home/user/Downloads/audio.ogg" small        # trocar modelo whisper
wpptrans "/home/user/Downloads/audio.ogg" resume small # modo + modelo juntos
```

Suportados: `tiny | base | small | medium | large | large-v3-turbo`  
Default: `large-v3-turbo`. Modo e modelo podem vir em qualquer ordem.

Variáveis de ambiente:
- `WPPTRANS_GEMINI_MODEL` — força um modelo Gemini específico
- `NO_COLOR` — desliga as cores

---

## Modos “apaga depois” (cuidado)

### Transcrever e apagar o original (apenas se estiver em `~/Downloads`)
```bash
wpptrans_rm "/home/user/Downloads/audio.ogg"
```

### Transcrever o `.ogg` mais recente em `~/Downloads`
```bash
wpptrans_last
```

### Transcrever o `.ogg` mais recente e apagar o original
```bash
wpptrans_last_rm
```

### Segurança
Os comandos `*_rm` **só apagam** se:
1) a transcrição terminou com sucesso (exit code 0)
2) o arquivo original está dentro de `~/Downloads/`

---

## Troubleshooting

### “whisper-cli: command not found”
Você ainda não tem whisper.cpp instalado.  
No Arch (exemplo): instale o pacote `whisper.cpp`.  
No Ubuntu: instale/compile whisper.cpp e garanta que `whisper-cli` esteja no `PATH`.

### “ffmpeg: command not found”
Instale:
- Ubuntu: `sudo apt install ffmpeg`
- Arch: `sudo pacman -S ffmpeg`

### “Modelo não encontrado”
Baixe o modelo (ex: small):
```bash
mkdir -p ~/.cache/whispercpp/models
curl -L -o ~/.cache/whispercpp/models/ggml-small.bin   https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
```

---

## Licença
MIT
