#!/usr/bin/env python3
"""
Etapa 9 — Teste Pratico
Comentar post real, acionar automacao e validar resposta ao vivo.
"""

import json
import shutil
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
RESPONDER_PATH = INSTAGRAM_DIR / "ig_auto_responder.py"

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
        # formato canonico: lista de triggers
        if isinstance(data, list):
            kws = []
            for t in data:
                kws.extend(t.get("keywords", []))
            return kws
        # formato legado: {"triggers": [...]}
        if isinstance(data, dict) and "triggers" in data:
            kws = []
            for t in data["triggers"]:
                kws.extend(t.get("keywords", t.get("keyword", [])))
            return kws
        return []
    except Exception:
        return []


def get_log_size(log_path):
    p = Path(log_path)
    return p.stat().st_size if p.exists() else 0


def get_log_tail(log_path, n=10):
    p = Path(log_path)
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        return lines[-n:] if lines else []
    except Exception:
        return []


def run_responder_now():
    """Executa o responder instalado diretamente e exibe saida ao vivo."""
    python_path = shutil.which("python3") or "python3"
    if not RESPONDER_PATH.exists():
        print(f"  [AVISO] Script nao encontrado: {RESPONDER_PATH}")
        return False
    print(f"  Executando: {python_path} {RESPONDER_PATH}")
    try:
        result = subprocess.run(
            [python_path, str(RESPONDER_PATH)],
            capture_output=True, text=True, timeout=60,
            cwd=str(Path.home()),
        )
        output = (result.stdout + result.stderr).strip()
        if output:
            print()
            for line in output.splitlines():
                print(f"    {line}")
            print()
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("  [AVISO] Responder excedeu 60s.")
        return False
    except Exception as e:
        print(f"  [AVISO] Erro ao executar responder: {e}")
        return False


def trigger_launchagent(label):
    if PLATFORM == "Darwin":
        try:
            import os
            uid = os.getuid()
            result = subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                print(f"  [OK] {label} acionado.")
            else:
                print(f"  [AVISO] kickstart {label}: {result.stderr.strip()}")
        except Exception as e:
            print(f"  [AVISO] Nao foi possivel acionar {label}: {e}")
    elif PLATFORM == "Linux":
        print("  [INFO] Linux: execute manualmente o script para testar.")


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


def print_permissions_table():
    print()
    print("  Tabela de permissoes da API Instagram:")
    print()
    print("  ┌─────────────────────────────┬─────────────────────────┐")
    print("  │ Acao                        │ Quem pode disparar      │")
    print("  ├─────────────────────────────┼─────────────────────────┤")
    print("  │ Detectar comentario         │ Qualquer pessoa         │")
    print("  │ Reply publico               │ Qualquer pessoa         │")
    print("  │ DM Private Reply            │ So seguidores ⚠️         │")
    print("  └─────────────────────────────┴─────────────────────────┘")
    print()
    print("  IMPORTANTE: para receber a DM automatica, o usuario que")
    print("  comentou precisa ser seguidor da sua conta.")
    print()


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

    print_permissions_table()

    keywords = load_keywords()
    if keywords:
        kw_display = ", ".join(f'"{kw}"' for kw in keywords[:5])
        print(f"  Keywords cadastradas: {kw_display}")
        print()
        print("  INSTRUCAO:")
        print(f"  Va ao seu Instagram e comente em qualquer post seu")
        print(f"  uma das palavras: {kw_display}")
        print(f"  (pode ser o 30o post — a automacao busca ate 50 posts)")
        print()
    else:
        print("  [AVISO] Nenhuma keyword encontrada em ig_triggers.json.")
        print("  Execute a Etapa 4 para cadastrar keywords.")
        print()

    ask("Quando fizer o comentario, pressione Enter para iniciar o teste")
    print()

    # Captura tamanho atual do log
    auto_log_size = get_log_size(IG_AUTO_LOG)

    print("  Disparando ig-auto agora (execucao direta)...")
    run_ok = run_responder_now()
    print()

    # Se execucao direta nao funcionou, tenta via kickstart
    if not run_ok and PLATFORM == "Darwin":
        print("  Tentando via LaunchAgent kickstart...")
        trigger_launchagent(LAUNCHCTL_AUTO)
        print()
        found = poll_log_for_keyword(IG_AUTO_LOG, "comment_id", timeout=60, initial_size=auto_log_size)
    else:
        # Verifica se o log foi atualizado pela execucao direta
        found = IG_AUTO_LOG.exists() and IG_AUTO_LOG.stat().st_size > auto_log_size

    print()

    if found or run_ok:
        tail = get_log_tail(IG_AUTO_LOG, n=5)
        if tail:
            print("  Ultimas entradas do log:")
            for line in tail:
                print(f"  > {line}")
            print()
        # Verifica se houve match de keyword
        if IG_AUTO_LOG.exists():
            log_text = IG_AUTO_LOG.read_text(encoding="utf-8", errors="ignore")
            new_text = log_text[auto_log_size:]
            if "comment_id" in new_text or "Keyword detectada" in new_text:
                print("  [OK] Comentario detectado e processado!")
            elif "0 comentarios processados" in new_text or "Ciclo concluido" in new_text:
                print("  [INFO] Ciclo rodou mas nenhum comentario novo com keyword foi detectado.")
                print("  Verifique se o comentario foi feito com a keyword correta.")
            else:
                print("  [INFO] Ciclo rodou. Verifique o log acima para detalhes.")
    else:
        print("  [AVISO] Nao detectamos atividade no log.")
        print("  Verifique se o LaunchAgent esta carregado e o token valido.")
        print()
        tail = get_log_tail(IG_AUTO_LOG, n=5)
        if tail:
            print("  Ultimas linhas do log:")
            for line in tail:
                print(f"  > {line}")
    print()

    resp_reply = ask("Voce recebeu o reply publico e/ou a DM? (s/N)", default="N").lower()
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

        print("  Disparando ig-dm agora...")
        if PLATFORM == "Darwin":
            trigger_launchagent(LAUNCHCTL_DM)
        print()

        found_dm = poll_log_for_keyword(IG_DM_LOG, "dm_respondida", timeout=60, initial_size=dm_log_size)
        print()

        if found_dm:
            tail_dm = get_log_tail(IG_DM_LOG, n=3)
            for line in tail_dm:
                print(f"  > {line}")
            print()
            print("  [OK] DM Agent respondeu!")
        else:
            print("  [AVISO] Nao detectamos resposta do DM Agent em 60s.")
            print("  Verifique se ANTHROPIC_API_KEY esta configurada (Etapa 6).")
            tail_dm = get_log_tail(IG_DM_LOG, n=5)
            if tail_dm:
                print("  Log DM:")
                for line in tail_dm:
                    print(f"  > {line}")
        print()

        resp_dm = ask("O agente respondeu sua DM? (s/N)", default="N").lower()
        print()
        if resp_dm in ("s", "sim", "y", "yes"):
            print("  Automacao Instagram 100% funcional!")
        else:
            print("  Verifique as configuracoes do DM Agent (Etapa 6) e tente novamente.")
    else:
        print("  Verifique se o reply publico e a DM foram enviados.")
        print("  Se nao chegaram:")
        print("  - Revise as permissoes (Etapa 3) e o token (Etapa 2)")
        print("  - Confirme que voce e seguidor da sua propria conta (para DM)")
        print("  - Verifique o log: tail -50 " + str(IG_AUTO_LOG))
    print()

    mark_checkpoint("step_9_teste_pratico", "done", "comentario_testado=true")

    print("  [OK] Etapa 9 concluida!")
    print()
    print("  Proximo: python3 setup/setup_final_s5.py")
    print()


if __name__ == "__main__":
    main()
