#!/usr/bin/env python3
"""
Etapa 4 — Comment Responder
Configurar keywords, replies automaticos e instalar LaunchAgent/cron.
"""

import json
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    IG_ENV_PATH,
    IG_STATE_PATH,
    IG_TRIGGERS_PATH,
    INSTAGRAM_DIR,
    PLATFORM,
    load_env_var,
    mark_checkpoint,
)
from ig_schemas import validate_triggers, make_trigger

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
TEMPLATES_DIR = ROOT_DIR / "templates"
IG_RESPONDER_SRC = ROOT_DIR / "scripts" / "ig_auto_responder.py"
LIB_SRC = ROOT_DIR / "scripts" / "lib.py"
IG_SCHEMAS_SRC = ROOT_DIR / "scripts" / "ig_schemas.py"


def ask(prompt, secret=False, default=None, validator=None):
    import getpass
    display = f"  {prompt}"
    if default:
        display += f" [{default}]"
    display += ": "
    while True:
        try:
            if secret:
                value = getpass.getpass(display).strip()
            else:
                value = input(display).strip()
            value = value if value else (default or "")
            if validator and value:
                ok, msg = validator(value)
                if not ok:
                    print(f"  {msg}")
                    continue
            return value
        except (KeyboardInterrupt, EOFError):
            print()
            print("  Setup cancelado.")
            sys.exit(0)


def is_url(value):
    if not value:
        return True, ""
    if not (value.startswith("http://") or value.startswith("https://")):
        return False, f"'{value}' nao parece uma URL valida (deve comecar com http:// ou https://)"
    return True, ""


def min_length(n):
    def _v(value):
        if len(value) < n:
            return False, f"Minimo {n} caracteres."
        return True, ""
    return _v


def collect_keywords():
    triggers = []
    print("  Cadastre as palavras-chave que vao disparar a automacao.")
    print("  Minimo: 1 palavra-chave. Pressione Enter em branco para finalizar.")
    print()

    idx = 1
    while True:
        print(f"  --- Palavra-chave #{idx} ---")
        keyword = ask(f"Palavra-chave #{idx} (Enter para finalizar)", validator=None)
        if not keyword:
            if not triggers:
                print("  Ao menos 1 palavra-chave e obrigatoria.")
                continue
            break

        link = ask(f"URL/link de destino para '{keyword}' (opcional)", validator=is_url)
        reply_text = ask(f"Mensagem do reply publico no comentario", validator=min_length(5))
        dm_text = ask(f"Mensagem da DM (Private Reply)", validator=min_length(5))

        triggers.append(make_trigger(
            keywords=[keyword],
            reply_text=reply_text,
            dm_text=dm_text,
            url=link,
        ))
        print(f"  [OK] Palavra-chave '{keyword}' cadastrada.")
        print()

        more = ask("Adicionar outra? (s/N)", default="N").lower()
        if more not in ("s", "sim", "y", "yes"):
            break

        idx += 1

    return triggers


def save_triggers(triggers):
    INSTAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    validate_triggers(triggers)
    IG_TRIGGERS_PATH.write_text(json.dumps(triggers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] ig_triggers.json salvo: {len(triggers)} keyword(s).")


def save_state():
    IG_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not IG_STATE_PATH.exists():
        IG_STATE_PATH.write_text(json.dumps({"processed_comment_ids": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  [OK] ig_state.json criado (vazio).")
    else:
        print("  [OK] ig_state.json ja existe.")


def copy_scripts():
    dest_dir = INSTAGRAM_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    for src in [IG_RESPONDER_SRC, LIB_SRC, IG_SCHEMAS_SRC]:
        dest = dest_dir / src.name
        if src.exists():
            shutil.copy2(str(src), str(dest))
            print(f"  [OK] {src.name} copiado para {dest_dir}")
        else:
            print(f"  [AVISO] {src.name} nao encontrado em scripts/.")


def _kickstart_and_verify(label, log_path, timeout=8):
    """Forca execucao via kickstart e verifica se apareceu entrada nova no log."""
    size_before = Path(log_path).stat().st_size if Path(log_path).exists() else 0
    try:
        import os
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
            capture_output=True, timeout=5,
        )
    except Exception:
        return False, "kickstart falhou"

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1)
        if Path(log_path).exists() and Path(log_path).stat().st_size > size_before:
            return True, "log atualizado"
    return False, "nenhuma entrada nova no log"


def install_launchagent(cadencia, posts_max):
    plist_name = "com.zxlab.ig-auto.plist"
    plist_src = TEMPLATES_DIR / plist_name

    responder_path = INSTAGRAM_DIR / "ig_auto_responder.py"
    python_path = shutil.which("python3") or "python3"
    log_path = INSTAGRAM_DIR / "logs" / "ig-auto.log"
    interval = cadencia * 60

    env_block = f"""    <key>EnvironmentVariables</key>
    <dict>
        <key>IG_POSTS_PROCESS_MAX</key>
        <string>{posts_max}</string>
    </dict>"""

    if plist_src.exists():
        content = plist_src.read_text(encoding="utf-8")
        content = content.replace("{{PYTHON}}", python_path)
        content = content.replace("{{RESPONDER_PATH}}", str(responder_path))
        content = content.replace("{{LOG_PATH}}", str(log_path))
        content = content.replace("{{INTERVAL}}", str(interval))
        content = content.replace("<key>RunAtLoad</key>\n    <false/>", "<key>RunAtLoad</key>\n    <true/>")
    else:
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.zxlab.ig-auto</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{responder_path}</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval}</integer>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
{env_block}
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""

    if PLATFORM == "Darwin":
        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        dest_plist = LAUNCH_AGENTS_DIR / plist_name
        dest_plist.write_text(content, encoding="utf-8")
        try:
            subprocess.run(["launchctl", "unload", str(dest_plist)], capture_output=True)
            subprocess.run(["launchctl", "load", str(dest_plist)], check=True, capture_output=True)
            print(f"  [OK] LaunchAgent instalado: {dest_plist}")
        except subprocess.CalledProcessError as e:
            print(f"  [AVISO] launchctl load falhou: {e}")
            return dest_plist, False

        print()
        print("  Verificando 1a execucao do agent...")
        ok, detail = _kickstart_and_verify("com.zxlab.ig-auto", log_path)
        if ok:
            print("  [OK] 1a execucao do agent: OK")
        else:
            print(f"  [AVISO] Agent instalado mas nao logou ({detail}).")
            print(f"  Para forcar manualmente:")
            import os
            print(f"    launchctl kickstart -k gui/{os.getuid()}/com.zxlab.ig-auto")
        return dest_plist, ok

    elif PLATFORM == "Linux":
        _install_cron(python_path, responder_path, cadencia)
        return None, True
    else:
        print(f"  [AVISO] Plataforma {PLATFORM}: instale manualmente o agendador.")
        return None, False


def _install_cron(python_path, responder_path, cadencia):
    cron_line = f"*/{cadencia} * * * * {python_path} {responder_path} >> ~/.operacao-ia/logs/week5/ig-auto.log 2>&1"
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        if str(responder_path) not in existing:
            new_cron = existing.rstrip() + "\n" + cron_line + "\n"
            proc = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
            if proc.returncode == 0:
                print(f"  [OK] Cron entry adicionado (a cada {cadencia} min).")
            else:
                print(f"  [AVISO] Falha ao adicionar cron: {proc.stderr}")
        else:
            print("  [OK] Cron entry ja existe.")
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel instalar cron: {e}")


def dry_run_installed(python_path=None):
    """Executa o script JA instalado em --dry-run para replicar o ambiente real do LaunchAgent."""
    installed = INSTAGRAM_DIR / "ig_auto_responder.py"
    if not installed.exists():
        print("  [AVISO] ig_auto_responder.py nao encontrado em destino. Pulando dry-run.")
        return False

    py = python_path or shutil.which("python3") or "python3"
    print(f"  Executando dry-run do script instalado: {installed}")
    try:
        result = subprocess.run(
            [py, str(installed), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path.home()),
        )
        output = (result.stdout + result.stderr).strip()
        if output:
            for line in output.splitlines()[-10:]:
                print(f"    {line}")
        if result.returncode == 0:
            print("  [OK] Dry-run concluido sem erros.")
            return True
        else:
            print(f"  [AVISO] Dry-run retornou codigo {result.returncode}.")
            return False
    except subprocess.TimeoutExpired:
        print("  [AVISO] Dry-run excedeu 30s.")
        return False
    except Exception as e:
        print(f"  [AVISO] Dry-run falhou: {e}")
        return False


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [████░░░░░░] Etapa 4 de 10")
    print()
    print("  Etapa 4 — Comment Responder")
    print()

    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    if not token:
        print("  [ERRO] IG_ACCESS_TOKEN nao encontrado. Execute a Etapa 2 primeiro.")
        sys.exit(1)

    triggers = collect_keywords()
    print()

    while True:
        cadencia_str = ask("Cadencia em minutos (5-60)", default="30")
        try:
            cadencia = int(cadencia_str)
            if 5 <= cadencia <= 60:
                break
            print("  Valor fora do range. Digite um numero entre 5 e 60.")
        except ValueError:
            print("  Valor invalido. Digite um numero inteiro entre 5 e 60.")
    print(f"  [OK] Cadencia: {cadencia} minutos.")
    print()

    while True:
        posts_str = ask("Quantos posts mais recentes monitorar? (10-200)", default="50")
        try:
            posts_max = int(posts_str)
            if 10 <= posts_max <= 200:
                break
            print("  Valor fora do range. Digite entre 10 e 200.")
        except ValueError:
            print("  Valor invalido.")
    print(f"  [OK] Posts monitorados: {posts_max}.")
    print()

    save_triggers(triggers)
    save_state()
    copy_scripts()
    print()

    print("  Instalando agendador...")
    _, agent_ok = install_launchagent(cadencia, posts_max)
    print()

    print("  Executando dry-run (simulacao sem envios reais)...")
    dry_ok = dry_run_installed()
    print()

    if agent_ok:
        status = "done"
    elif dry_ok:
        status = "partial"
        print("  [AVISO] Agent instalado mas 1a execucao nao confirmada.")
    else:
        status = "partial"
        print("  [AVISO] Etapa 4 com problemas. Verifique os logs antes de continuar.")

    import os
    print()
    print(f"  Para forcar execucao agora:")
    print(f"    launchctl kickstart -k gui/{os.getuid()}/com.zxlab.ig-auto")
    print()

    mark_checkpoint("step_4_comment_responder", status, f"keywords={len(triggers)} cadencia={cadencia}min posts_max={posts_max}")

    print("  [OK] Etapa 4 concluida!")
    print()
    print("  Proximo: python3 setup/setup_dm_kb.py")
    print()


if __name__ == "__main__":
    main()
