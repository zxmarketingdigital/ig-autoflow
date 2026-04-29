#!/usr/bin/env python3
"""
Etapa 9 — Teste Pratico
Comentar post real, acionar automacao e validar resposta ao vivo.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    IG_TRIGGERS_PATH,
    INSTAGRAM_DIR,
    PLATFORM,
    mark_checkpoint,
)

IG_AUTO_LOG = INSTAGRAM_DIR / "logs" / "ig-auto.log"
IG_DM_LOG = INSTAGRAM_DIR / "logs" / "ig-dm.log"

LAUNCHCTL_AUTO = "com.zxlab.ig-auto"
LAUNCHCTL_DM = "com.zxlab.ig-dm"


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


def load_keywords():
    if not IG_TRIGGERS_PATH.exists():
        return []
    try:
        data = json.loads(IG_TRIGGERS_PATH.read_text(encoding="utf-8"))
        return [t["keyword"] for t in data.get("triggers", [])]
    except Exception:
        return []


def get_log_size(log_path):
    p = Path(log_path)
    if not p.exists():
        return 0
    return p.stat().st_size


def get_log_tail(log_path, n=5):
    p = Path(log_path)
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        return lines[-n:] if lines else []
    except Exception:
        return []


def trigger_launchagent(label):
    if PLATFORM == "Darwin":
        try:
            result = subprocess.run(
                ["launchctl", "start", label],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                print(f"  [OK] {label} acionado.")
            else:
                print(f"  [AVISO] launchctl start {label}: {result.stderr.strip()}")
        except Exception as e:
            print(f"  [AVISO] Nao foi possivel acionar {label}: {e}")
    elif PLATFORM == "Linux":
        print(f"  [INFO] Linux: execute manualmente o script para testar.")
    else:
        print(f"  [INFO] Execute o agendador manualmente para testar.")


def poll_log_for_keyword(log_path, keyword, timeout=120, initial_size=0):
    start = time.time()
    print(f"  Aguardando '{keyword}' no log por ate {timeout}s", end="", flush=True)
    while time.time() - start < timeout:
        p = Path(log_path)
        if p.exists():
            current_size = p.stat().st_size
            if current_size > initial_size:
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    if keyword in text[initial_size:]:
                        print(" encontrado!")
                        return True
                except Exception:
                    pass
        print(".", end="", flush=True)
        time.sleep(5)
    print(" timeout.")
    return False


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [█████████░] Etapa 9 de 10")
    print()
    print("  Etapa 9 — Teste Pratico")
    print()

    keywords = load_keywords()
    if keywords:
        kw_display = ", ".join(f'"{kw}"' for kw in keywords[:5])
        print(f"  Keywords cadastradas: {kw_display}")
        print()
        print("  INSTRUCAO:")
        print(f"  Va ao seu Instagram e comente em qualquer post seu")
        print(f"  uma das palavras: {kw_display}")
        print()
    else:
        print("  [AVISO] Nenhuma keyword encontrada em ig_triggers.json.")
        print("  Execute a Etapa 4 para cadastrar keywords.")
        print()

    ask("Quando fizer o comentario, pressione Enter para iniciar o teste")
    print()

    # Captura tamanho atual do log
    auto_log_size = get_log_size(IG_AUTO_LOG)

    print("  Acionando ig-auto agora...")
    trigger_launchagent(LAUNCHCTL_AUTO)
    print()

    found = poll_log_for_keyword(IG_AUTO_LOG, "comment_id", timeout=120, initial_size=auto_log_size)
    print()

    if found:
        tail = get_log_tail(IG_AUTO_LOG, n=3)
        for line in tail:
            print(f"  > {line}")
        print()
        print("  [OK] Comentario detectado e processado!")
    else:
        print("  [AVISO] Nao detectamos o comentario no log em 120s.")
        print("  Verifique se o LaunchAgent esta carregado e o token valido.")
        tail = get_log_tail(IG_AUTO_LOG, n=5)
        if tail:
            print("  Ultimas linhas do log:")
            for line in tail:
                print(f"  > {line}")
    print()

    resp_reply = ask("Voce recebeu o reply publico e a DM? (s/N)", default="N").lower()
    print()

    if resp_reply in ("s", "sim", "y", "yes"):
        print("  Otimo! Agora vamos testar o DM Agent.")
        print()
        print("  INSTRUCAO:")
        print("  Responda a DM que voce recebeu com: 'quero saber mais'")
        print()
        ask("Quando enviar a resposta na DM, pressione Enter")
        print()

        dm_log_size = get_log_size(IG_DM_LOG)

        print("  Acionando ig-dm agora...")
        trigger_launchagent(LAUNCHCTL_DM)
        print()

        found_dm = poll_log_for_keyword(IG_DM_LOG, "dm_respondida", timeout=60, initial_size=dm_log_size)
        print()

        if found_dm:
            print("  [OK] DM Agent respondeu!")
        else:
            print("  [AVISO] Nao detectamos resposta do DM Agent em 60s.")
            print("  Verifique se o OmniRoute esta rodando.")
        print()

        resp_dm = ask("O agente respondeu sua DM? (s/N)", default="N").lower()
        print()
        if resp_dm in ("s", "sim", "y", "yes"):
            print("  Automacao Instagram 100% funcional!")
        else:
            print("  Verifique as configuracoes do DM Agent (Etapa 6) e tente novamente.")
    else:
        print("  Verifique se o reply publico e a DM foram enviados.")
        print("  Se nao chegaram, revise as permissoes (Etapa 3) e o token (Etapa 2).")
    print()

    mark_checkpoint("step_9_teste_pratico", "done", "comentario_testado=true")

    print("  [OK] Etapa 9 concluida!")
    print()
    print("  Proximo: python3 setup/setup_final_s5.py")
    print()


if __name__ == "__main__":
    main()
