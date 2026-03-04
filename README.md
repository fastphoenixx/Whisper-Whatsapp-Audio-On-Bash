# Whisper WhatsApp Audio (wpptrans)

Scripts para transcrever áudios do WhatsApp (geralmente `.ogg`/Opus) usando **whisper.cpp** (`whisper-cli`) + **ffmpeg**.

O foco aqui é fluxo rápido:
- colou/arrastou o arquivo → transcreveu no terminal
- opção de apagar o WAV temporário
- opção de apagar o áudio original (com guarda)

---

## Requisitos

### Dependências
- `ffmpeg`
- `whisper-cli` (whisper.cpp)
- `python` (usado só para decodificar `file:///...%20...` de forma robusta)

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

Trocar modelo (último argumento):
```bash
wpptrans "/home/user/Downloads/audio.ogg" base
```

Modelos suportados:
`tiny | base | small | medium | large`  
Default: `small`

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
