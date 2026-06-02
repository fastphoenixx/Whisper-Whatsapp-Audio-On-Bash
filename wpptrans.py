#!/usr/bin/env python3
"""wpptrans — transcribe WhatsApp audio (.ogg/Opus) via whisper.cpp, render it
nicely in the terminal, and optionally enrich with Gemini (summary, tasks,
likely reply, key points).

Invoked by the fish wrappers in fish/wpptrans.fish, but usable standalone:

    wpptrans.py AUDIO [AUDIO...] [MODE...] [MODEL]
    wpptrans.py --last [MODE...] [MODEL]
    wpptrans.py --batch N [MODE...] [MODEL]
    wpptrans.py --last --rm [MODE...]

MODE selects which Gemini sections to show (default: all):
    resume|resumo|summary        -> summary
    tasks|tarefas|task           -> task list
    reply|resposta|responder     -> likely reply
    bullet|bulletpoint|pontos    -> key points
    all|full                     -> everything (default)
    raw|texto|none               -> transcription only (no AI)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home()
DOWNLOADS = HOME / "Downloads"
MODELS_DIR = HOME / ".cache" / "whispercpp" / "models"
DEFAULT_MODEL = "large-v3-turbo"
GEMINI_MODEL = os.environ.get("WPPTRANS_GEMINI_MODEL", "")  # empty -> CLI default
AUDIO_EXTS = {".ogg", ".opus", ".m4a", ".mp3", ".wav", ".aac", ".flac"}

KNOWN_MODELS = {"tiny", "base", "small", "medium", "large", "large-v3-turbo"}

# Largest → smallest. Used to walk down when the preferred model doesn't fit in VRAM.
MODEL_FALLBACK_CHAIN = ["large", "large-v3-turbo", "medium", "small", "base", "tiny"]

# MiB of VRAM to reserve on top of the model file size (CUDA context + KV cache + activations).
VRAM_OVERHEAD_MIB = 500

# mode keyword -> canonical section
MODE_ALIASES = {
    "resume": "summary", "resumo": "summary", "summary": "summary",
    "tasks": "tasks", "tarefas": "tasks", "task": "tasks",
    "reply": "reply", "resposta": "reply", "responder": "reply",
    "bullet": "keypoints", "bulletpoint": "keypoints", "bullets": "keypoints",
    "pontos": "keypoints", "keypoints": "keypoints",
    "all": "all", "full": "all", "tudo": "all",
    "raw": "raw", "texto": "raw", "none": "raw",
}
ALL_SECTIONS = ["summary", "tasks", "reply", "keypoints"]

SECTION_TITLES = {
    "summary": "Resumo",
    "tasks": "Tarefas",
    "reply": "Resposta provável",
    "keypoints": "Pontos-chave",
}

# ─── ANSI ────────────────────────────────────────────────────────────────────
class C:
    reset = "\033[0m"
    dim = "\033[2m"
    bold = "\033[1m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    blue = "\033[34m"


def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


COLOR = supports_color()


def paint(text: str, *codes: str) -> str:
    if not COLOR or not codes:
        return text
    return "".join(codes) + text + C.reset


def term_width(maxw: int = 100) -> int:
    return min(shutil.get_terminal_size((80, 24)).columns, maxw)


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


# ─── core steps ────────────────────────────────────────────────────────────--
def decode_path(raw: str) -> str:
    if raw.startswith("file://"):
        raw = raw[len("file://"):]
    return urllib.parse.unquote(raw)


def model_path(model: str) -> Path:
    return MODELS_DIR / f"ggml-{model}.bin"


def vram_free_mib() -> int | None:
    """Free VRAM (MiB) on GPU 0. Returns None when no NVIDIA GPU is available
    or the query fails — caller should skip the VRAM check in that case."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    line = out.stdout.strip().splitlines()[0].strip() if out.stdout.strip() else ""
    try:
        return int(line)
    except ValueError:
        return None


def model_size_mib(model: str) -> int | None:
    mp = model_path(model)
    if not mp.is_file():
        return None
    return mp.stat().st_size // (1024 * 1024)


def pick_model(preferred: str) -> str:
    """Return the preferred whisper model if it fits in free VRAM; otherwise
    the largest locally-installed smaller model that fits. Falls back to the
    preferred model when there is no GPU info, the user opted out, or nothing
    smaller is installed — letting whisper-cli surface its own error."""
    if os.environ.get("WPPTRANS_NO_VRAM_CHECK"):
        return preferred
    free = vram_free_mib()
    if free is None:
        return preferred

    def fits(m: str) -> bool:
        size = model_size_mib(m)
        return size is not None and size + VRAM_OVERHEAD_MIB <= free

    if fits(preferred):
        return preferred

    if preferred in MODEL_FALLBACK_CHAIN:
        candidates = MODEL_FALLBACK_CHAIN[MODEL_FALLBACK_CHAIN.index(preferred) + 1:]
    else:
        candidates = MODEL_FALLBACK_CHAIN

    for m in candidates:
        if fits(m):
            preferred_size = model_size_mib(preferred)
            preferred_label = (
                f"{preferred} (~{preferred_size} MiB)" if preferred_size is not None
                else preferred
            )
            eprint(paint(
                f"  ⚠ VRAM insuficiente para {preferred_label}: só "
                f"{free} MiB livres — usando '{m}'", C.yellow
            ))
            return m

    return preferred


def audio_duration(path: str) -> str:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=20,
        )
        secs = float(out.stdout.strip())
        m, s = divmod(int(round(secs)), 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "?:??"


def to_wav(src: str) -> str | None:
    fd, tmp = tempfile.mkstemp(prefix="wpptrans_", suffix=".wav")
    os.close(fd)
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1",
         "-c:a", "pcm_s16le", tmp, "-loglevel", "error"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        eprint(paint("Erro: falha na conversão com ffmpeg", C.red))
        if proc.stderr.strip():
            eprint(C.dim + proc.stderr.strip() + C.reset if COLOR else proc.stderr.strip())
        os.remove(tmp)
        return None
    return tmp


def reflow(raw: str) -> str:
    """whisper -nt prints one segment per line; rejoin into flowing text."""
    parts = [ln.strip() for ln in raw.splitlines()]
    text = " ".join(p for p in parts if p)
    return " ".join(text.split())


def transcribe(wav: str, model: str) -> str | None:
    mp = model_path(model)
    if not mp.is_file():
        eprint(paint(f"Erro: modelo '{model}' não encontrado em {mp}", C.red))
        return None
    proc = subprocess.run(
        ["whisper-cli", "-m", str(mp), "-f", wav, "-l", "pt",
         "--no-prints", "-nt"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        eprint(paint("Erro: whisper-cli falhou", C.red))
        if proc.stderr.strip():
            eprint(proc.stderr.strip())
        return None
    return reflow(proc.stdout)


# ─── rendering ─────────────────────────────────────────────────────────────--
def panel(title: str, body: str, border: str = C.cyan) -> None:
    import textwrap

    width = term_width()
    inner = width - 4
    title = f" {title} "
    if len(title) > inner:
        title = title[: inner - 1] + "…"
    fill = "─" * max(0, inner - len(title))
    print(paint("┌─" + title + fill + "─┐", border))
    if not body.strip():
        body = "(vazio)"
    for para in body.split("\n"):
        wrapped = textwrap.wrap(para, width=inner) or [""]
        for line in wrapped:
            print(paint("│ ", border) + line.ljust(inner) + paint(" │", border))
    print(paint("└─" + "─" * len(title) + fill + "─┘", border))


def render_markdown(md: str) -> None:
    sys.stdout.flush()  # keep ordering when piped: bat writes to the fd directly
    if shutil.which("bat"):
        subprocess.run(
            ["bat", "--language", "md", "--style", "plain",
             "--color", "always" if COLOR else "never", "--paging", "never"],
            input=md, text=True,
        )
    else:
        print(md)


# ─── gemini ──────────────────────────────────────────────────────────────────
_SECTION_PROMPTS_SINGLE = {
    "summary": "Resuma em 1 a 3 frases.",
    "tasks": "Liste em checklist (- [ ]) as tarefas/pendências/compromissos. Se não houver, escreva '- (nenhuma)'.",
    "reply": "Escreva um rascunho curto e natural de resposta que eu poderia mandar de volta no WhatsApp.",
    "keypoints": "Bullets com os pontos importantes, nomes, datas e valores mencionados.",
}

_SECTION_PROMPTS_BATCH = {
    "summary": (
        "Para CADA áudio, escreva uma linha no formato "
        "`- [Áudio N — nome]: <1 frase concreta>`. "
        "Cubra todos os áudios na ordem. Nada de frase guarda-chuva genérica "
        "tipo 'os áudios tratam de diversos assuntos'."
    ),
    "tasks": (
        "Checklist consolidado de TODAS as tarefas/pendências/compromissos. "
        "Cada item no formato `- [ ] <ação> — [Áudio N]`. "
        "Inclua prazos, nomes e valores quando mencionados. "
        "Se nenhum áudio tiver tarefa, escreva `- (nenhuma)`."
    ),
    "reply": (
        "Para cada áudio que pede ou espera resposta, escreva um rascunho separado "
        "no formato `**[Áudio N — nome]**` seguido do texto da resposta em uma "
        "linha em branco. Pule áudios que não pedem resposta."
    ),
    "keypoints": (
        "Bullets com TODOS os fatos concretos extraíveis: nomes próprios, datas, "
        "horários, locais, valores monetários, decisões, números, prazos. "
        "Cada bullet no formato `- <fato> — [Áudio N]`. "
        "Não resuma — liste. Prefira granularidade alta."
    ),
}


def build_prompt(sections: list[str], jobs: list["Job"]) -> str:
    batch = len(jobs) > 1
    prompts = _SECTION_PROMPTS_BATCH if batch else _SECTION_PROMPTS_SINGLE
    wanted = "\n".join(
        f"## {SECTION_TITLES[s]}\n{prompts[s]}" for s in sections
    )
    if not batch:
        intro = (
            "Você recebe a transcrição de um áudio de WhatsApp (pode ter erros de "
            "transcrição). Responda em português do Brasil, em markdown, gerando "
            "EXATAMENTE as seções abaixo (com esses títulos ##), nada além disso. "
            "Seja conciso."
        )
        body = f"---\nTranscrição:\n{jobs[0].text}\n"
    else:
        intro = (
            f"Você recebe as transcrições de {len(jobs)} áudios de WhatsApp em "
            "sequência (podem ter erros). Gere EXATAMENTE as seções abaixo (com "
            "esses títulos ##), nada além disso, em português do Brasil em "
            "markdown.\n\n"
            "Regras OBRIGATÓRIAS:\n"
            "1. Cubra TODOS os áudios — nenhum pode ser ignorado.\n"
            "2. Toda afirmação, tarefa, ponto ou rascunho deve identificar a "
            "origem com a tag `[Áudio N]` (use a numeração das transcrições "
            "abaixo).\n"
            "3. Seja ESPECÍFICO e CONCRETO. Cite nomes, datas, horários, valores, "
            "decisões literais. Proibido escrever frases genéricas tipo 'discute "
            "vários assuntos', 'fala sobre diversos temas' ou 'aborda diferentes "
            "pontos'.\n"
            "4. Prefira MAIS detalhe a menos. Não tente comprimir; granularidade "
            "é o objetivo aqui.\n"
            "5. Não invente nada que não esteja na transcrição."
        )
        chunks = "\n\n".join(
            f"### Áudio {i} — {job.name} ({job.duration})\n{job.text}"
            for i, job in enumerate(jobs, 1)
        )
        body = f"---\nTranscrições:\n{chunks}\n"
    return f"{intro}\n\n{wanted}\n\n{body}"


def run_gemini(prompt: str) -> str | None:
    if not shutil.which("gemini"):
        eprint(paint("Aviso: gemini CLI não encontrado — pulando análise IA.", C.yellow))
        return None
    cmd = ["gemini", "--skip-trust", "-p", prompt]
    if GEMINI_MODEL:
        cmd[1:1] = ["-m", GEMINI_MODEL]
    # Run from a clean dir so the CLI doesn't scan the cwd tree.
    workdir = str(Path(__file__).resolve().parent)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=workdir,
            timeout=180, env={**os.environ, "GEMINI_CLI_TRUST_WORKSPACE": "true"},
        )
    except subprocess.TimeoutExpired:
        eprint(paint("Aviso: Gemini demorou demais (timeout) — pulando análise.", C.yellow))
        return None
    out = proc.stdout.strip()
    if proc.returncode != 0 and not out:
        eprint(paint("Aviso: Gemini falhou — pulando análise.", C.yellow))
        if proc.stderr.strip():
            eprint(C.dim + proc.stderr.strip()[:500] + C.reset if COLOR else proc.stderr.strip()[:500])
        return None
    return out or None


# ─── job ───────────────────────────────────────────────────────────────────--
@dataclass
class Options:
    files: list[str] = field(default_factory=list)
    model: str = DEFAULT_MODEL
    sections: list[str] = field(default_factory=lambda: list(ALL_SECTIONS))
    ai: bool = True
    rm: bool = False


@dataclass
class Job:
    src: str
    name: str
    duration: str
    text: str


def transcribe_one(src: str, opts: Options, idx: int = 0, total: int = 1) -> Job | None:
    if not os.path.isfile(src):
        eprint(paint(f"Erro: arquivo não encontrado: {src}", C.red))
        return None

    counter = f"[{idx}/{total}] " if total > 1 else ""
    name = os.path.basename(src)
    print()
    print(paint(f"{counter}{C.bold}{name}{C.reset}", C.blue) if COLOR else f"{counter}{name}")

    wav = to_wav(src)
    if wav is None:
        return None
    try:
        dur = audio_duration(src)
        model = pick_model(opts.model)
        eprint(paint(f"  transcrevendo ({model}, {dur})…", C.dim))
        text = transcribe(wav, model)
    finally:
        os.remove(wav)

    if text is None:
        return None

    panel(f"Transcrição · {dur} · {model}", text, border=C.cyan)
    return Job(src=src, name=name, duration=dur, text=text)


def analyze_all(jobs: list[Job], opts: Options) -> None:
    usable = [j for j in jobs if j.text.strip()]
    if not usable:
        return
    if len(usable) == 1:
        eprint(paint("  analisando com Gemini…", C.dim))
    else:
        eprint(paint(
            f"  analisando {len(usable)} transcrições juntas com Gemini…", C.dim
        ))
    result = run_gemini(build_prompt(opts.sections, usable))
    if not result:
        return
    print()
    if len(usable) == 1:
        print(paint("── Análise (Gemini) ──", C.green, C.bold))
    else:
        print(paint(
            f"── Análise consolidada · {len(usable)} áudios ──",
            C.green, C.bold,
        ))
    render_markdown(result)


def cleanup(src: str) -> None:
    real = os.path.realpath(src)
    if os.path.commonpath([real, str(DOWNLOADS.resolve())]) == str(DOWNLOADS.resolve()):
        os.remove(src)
        print(paint(f"(arquivo removido: {src})", C.dim))
    else:
        eprint(paint(f"Aviso: remoção permitida apenas em ~/Downloads/ — mantido: {src}", C.yellow))


# ─── arg parsing ─────────────────────────────────────────────────────────────
def newest_ogg(n: int = 1) -> list[str]:
    files = sorted(
        (p for p in DOWNLOADS.glob("*.ogg")),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    return [str(p) for p in files[:n]]


def parse_args(argv: list[str]) -> Options | None:
    opts = Options()
    use_last = False
    batch_n: int | None = None
    sections: list[str] = []
    raw_mode = False
    positionals: list[str] = []

    it = iter(argv)
    for a in it:
        if a in ("--rm",):
            opts.rm = True
        elif a in ("--last",):
            use_last = True
        elif a in ("--no-ai",):
            opts.ai = False
        elif a in ("--batch",):
            nxt = next(it, "")
            batch_n = int(nxt) if nxt.isdigit() else 0  # 0 -> all
        elif a.startswith("--"):
            eprint(paint(f"Aviso: flag desconhecida ignorada: {a}", C.yellow))
        else:
            positionals.append(a)

    # classify positionals: model | mode | file
    for p in positionals:
        low = p.lower()
        if low in KNOWN_MODELS:
            opts.model = low
        elif low in MODE_ALIASES:
            canon = MODE_ALIASES[low]
            if canon == "raw":
                raw_mode = True
            elif canon == "all":
                sections = list(ALL_SECTIONS)
            else:
                sections.append(canon)
        else:
            opts.files.append(decode_path(p))

    if sections:
        # dedupe, keep canonical order
        opts.sections = [s for s in ALL_SECTIONS if s in sections]
    if raw_mode:
        opts.ai = False

    # resolve source files
    if batch_n is not None:
        opts.files = newest_ogg(batch_n if batch_n > 0 else 10_000)
        if not opts.files:
            eprint(paint("Nenhum arquivo .ogg encontrado em ~/Downloads/", C.red))
            return None
    elif use_last:
        latest = newest_ogg(1)
        if not latest:
            eprint(paint("Nenhum arquivo .ogg encontrado em ~/Downloads/", C.red))
            return None
        opts.files = latest

    if not opts.files:
        eprint("Uso: wpptrans <arquivo.ogg> [modo] [modelo]")
        eprint("Modos: resume | tarefas | reply | bullet | all | raw")
        eprint("Modelos: tiny | base | small | medium | large | large-v3-turbo")
        return None

    return opts


def main(argv: list[str]) -> int:
    opts = parse_args(argv)
    if opts is None:
        return 1
    total = len(opts.files)
    jobs: list[Job] = []
    failed = 0

    # Phase 1 — transcribe every file before touching Gemini.
    for i, f in enumerate(opts.files, 1):
        job = transcribe_one(f, opts, i, total)
        if job is None:
            failed += 1
        else:
            jobs.append(job)

    # Phase 2 — single Gemini call covering all transcriptions as one context.
    if opts.ai and jobs:
        analyze_all(jobs, opts)

    # Phase 3 — only remove files that made it through transcription.
    if opts.rm and jobs:
        print()
        for job in jobs:
            cleanup(job.src)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        eprint("\nInterrompido.")
        sys.exit(130)
