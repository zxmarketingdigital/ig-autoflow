#!/usr/bin/env python3
"""
Etapa 1 — Base Semana 5
Boas-vindas, diagnostico e criacao da estrutura para S5 (Automacao Instagram).
"""

import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    CONFIG_PATH,
    INSTAGRAM_DIR,
    PLATFORM,
    WEEK5_LOGS_DIR,
    SESSION_LOGS_DIR,
    ensure_structure,
    load_config,
    mark_checkpoint,
    now_iso,
    save_config,
)


def ask(prompt, secret=False, default=None):
    import getpass
    display = f"  {prompt}"
    if default:
        display += f" [{default}]"
    display += ": "
    try:
        if secret:
            value = getpass.getpass(display).strip()
        else:
            value = input(display).strip()
        return value if value else (default or "")
    except (KeyboardInterrupt, EOFError):
        print()
        print("  Setup cancelado.")
        sys.exit(0)


def detect_scheduler():
    if PLATFORM == "Darwin":
        path = shutil.which("launchctl")
        if path:
            print(f"  [OK] launchctl encontrado: {path}")
        else:
            print("  [AVISO] launchctl nao encontrado (incomum no macOS).")
        return "launchctl"
    elif PLATFORM == "Windows":
        path = shutil.which("schtasks")
        if path:
            print(f"  [OK] schtasks encontrado: {path}")
        else:
            print("  [AVISO] schtasks nao encontrado no PATH.")
        return "schtasks"
    else:
        path = shutil.which("cron") or shutil.which("crontab")
        if path:
            print(f"  [OK] cron encontrado: {path}")
        else:
            print("  [AVISO] cron nao encontrado. Instale com: sudo apt install cron")
        return "cron"


def print_plan():
    steps = [
        ("Etapa 1",  "Base S5               — Ambiente e estrutura de diretorios (este script)"),
        ("Etapa 2",  "Meta App              — Criar app + token + smoke tests API"),
        ("Etapa 3",  "App Review            — Privacy Policy + submissao + aguardar Live"),
        ("Etapa 4",  "Comment Responder     — Keywords, replies automaticos e LaunchAgent"),
        ("Etapa 5",  "DM Knowledge Base     — Cadastrar produtos e base de conhecimento"),
        ("Etapa 6",  "DM Agent              — OmniRoute + Evolution + agente de DM"),
        ("Etapa 7",  "Mission Control 5.0   — Widgets IG no dashboard"),
        ("Etapa 8",  "Auditoria Tecnica     — Verificacao dos 11 componentes Instagram"),
        ("Etapa 9",  "Teste Pratico         — Comentar post real e validar automacao"),
        ("Etapa 10", "Finalizacao           — Log final + Supabase + ZX Control 2.0"),
    ]
    print()
    print("  Plano completo — 10 etapas:")
    print()
    for label, desc in steps:
        print(f"    {label}: {desc}")
    print()


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║                                                      ║")
    print("  ║   ZX LAB — Rafael Castro                             ║")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ║                                                      ║")
    print("  ║   © 2026 ZX LAB · Todos os direitos reservados       ║")
    print("  ║   Reproducao ou redistribuicao sem autorizacao       ║")
    print("  ║   expressa e proibida.                               ║")
    print("  ║                                                      ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [█░░░░░░░░░] Etapa 1 de 10")
    print()
    print("  Bem-vindo(a) a Semana 5 do ZX Control!")
    print("  Nesta semana voce vai automatizar o Instagram Business.")
    print()

    print("  Verificando o ambiente...")
    # Este setup nao exige nenhum setup anterior: se nao existir config.json,
    # cria o minimo; se existir uma instalacao anterior, aproveita o que for valido.
    existia = CONFIG_PATH.exists()
    config = load_config()
    if existia:
        print("  [OK] Instalacao anterior encontrada — aproveitando o que for valido.")
    else:
        print("  [OK] Primeira instalacao — config.json minimo criado.")
    print()

    print(f"  Sistema operacional: {PLATFORM}")
    config["platform"] = PLATFORM

    pv = sys.version.split()[0]
    major, minor = sys.version_info.major, sys.version_info.minor
    print(f"  Python: {pv}")
    if major < 3 or (major == 3 and minor < 9):
        print()
        print(f"  ERRO: Python 3.9+ necessario. Versao atual: {pv}")
        print("  Atualize o Python em https://python.org/downloads")
        sys.exit(1)
    print("  [OK] Python >= 3.9 disponivel.")
    print()

    print("  Verificando agendador de tarefas...")
    scheduler = detect_scheduler()
    config["scheduler"] = scheduler
    print()

    print("  Criando estrutura de diretorios...")
    ensure_structure()
    print("  [OK] Estrutura base criada em ~/.operacao-ia/")

    for subdir, label in [
        (INSTAGRAM_DIR,               "INSTAGRAM_DIR"),
        (INSTAGRAM_DIR / "logs",      "INSTAGRAM_DIR/logs"),
        (WEEK5_LOGS_DIR,              "WEEK5_LOGS_DIR"),
        (SESSION_LOGS_DIR,            "SESSION_LOGS_DIR"),
    ]:
        subdir.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] {label}: {subdir}")
    print()

    print_plan()

    save_config(config)
    print("  [OK] config.json atualizado.")
    print()

    detail = f"Platform:{PLATFORM} Python:{pv} Scheduler:{scheduler}"
    mark_checkpoint("step_1_base_s5", "done", detail)

    print("  [OK] Etapa 1 concluida!")
    print()
    print("  Proximo: python3 setup/setup_meta_app.py")
    print()


if __name__ == "__main__":
    main()
