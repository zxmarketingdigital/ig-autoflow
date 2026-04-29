#!/usr/bin/env python3
"""
Etapa 4 — Comment Responder
Configurar keywords, replies automaticos e instalar LaunchAgent/cron.
"""

import json
import shutil
import subprocess
import sys
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

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
TEMPLATES_DIR = ROOT_DIR / "templates"
IG_RESPONDER_SRC = ROOT_DIR / "scripts" / "ig_auto_responder.py"


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


def collect_keywords():
    triggers = []
    print("  Cadastre as palavras-chave que vao disparar a automacao.")
    print("  Minimo: 1 palavra-chave. Pressione Enter em branco para finalizar.")
    print()

    idx = 1
    while True:
        print(f"  --- Palavra-chave #{idx} ---")
        keyword = ask(f"Palavra-chave #{idx} (Enter para finalizar)")
        if not keyword:
            if not triggers:
                print("  Ao menos 1 palavra-chave e obrigatoria.")
                continue
            break

        link = ask(f"URL/link de destino para '{keyword}'")
        reply_text = ask(f"Mensagem do reply publico no comentario")
        dm_text = ask(f"Mensagem da DM (Private Reply)")

        triggers.append({
            "keywords": [keyword.lower().strip()],
            "url": link,
            "reply_text": reply_text,
            "dm_text": dm_text,
        })
        print(f"  [OK] Palavra-chave '{keyword}' cadastrada.")
        print()

        more = ask("Adicionar outra? (s/N)", default="N").lower()
        if more not in ("s", "sim", "y", "yes"):
            break

        idx += 1

    return triggers


def save_triggers(triggers):
    INSTAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    IG_TRIGGERS_PATH.write_text(json.dumps(triggers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] ig_triggers.json salvo: {len(triggers)} keyword(s).")


def save_state():
    IG_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not IG_STATE_PATH.exists():
        IG_STATE_PATH.write_text(json.dumps({"processed_comment_ids": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] ig_state.json criado (vazio).")
    else:
        print(f"  [OK] ig_state.json ja existe.")


def copy_responder():
    dest = INSTAGRAM_DIR / "ig_auto_responder.py"
    if IG_RESPONDER_SRC.exists():
        shutil.copy2(str(IG_RESPONDER_SRC), str(dest))
        print(f"  [OK] ig_auto_responder.py copiado para {INSTAGRAM_DIR}")
    else:
        dest.touch()
        print(f"  [AVISO] ig_auto_responder.py nao encontrado em scripts/. Arquivo vazio criado.")
        print(f"  Adicione o script em: {IG_RESPONDER_SRC}")


def install_launchagent(cadencia):
    plist_name = "com.zxlab.ig-auto.plist"
    plist_src = TEMPLATES_DIR / plist_name

    responder_path = INSTAGRAM_DIR / "ig_auto_responder.py"
    python_path = shutil.which("python3") or "python3"
    log_path = INSTAGRAM_DIR / "logs" / "ig-auto.log"
    interval = cadencia * 60

    if plist_src.exists():
        content = plist_src.read_text(encoding="utf-8")
        content = content.replace("{{PYTHON}}", python_path)
        content = content.replace("{{RESPONDER_PATH}}", str(responder_path))
        content = content.replace("{{LOG_PATH}}", str(log_path))
        content = content.replace("{{INTERVAL}}", str(interval))
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
    <key>RunAtLoad</key>
    <false/>
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
    elif PLATFORM == "Linux":
        _install_cron(python_path, responder_path, cadencia)
    else:
        print(f"  [AVISO] Plataforma {PLATFORM}: instale manualmente o agendador.")


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
            print(f"  [OK] Cron entry ja existe.")
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel instalar cron: {e}")


def get_first_media_id(token):
    import urllib.error
    url = f"https://graph.instagram.com/v22.0/me/media?access_token={token}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            posts = data.get("data", [])
            return posts[0]["id"] if posts else None
    except Exception:
        return None


def dry_run(triggers, token):
    import urllib.request as _req

    media_id = get_first_media_id(token)
    if not media_id:
        print("  [AVISO] Nao foi possivel obter posts para dry-run.")
        return

    url = f"https://graph.instagram.com/v22.0/{media_id}/comments?access_token={token}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            comments = data.get("data", [])[:5]
    except Exception:
        comments = []

    print(f"  Dry-run em {len(comments)} comentario(s) recentes (sem enviar nada):")
    print()
    for c in comments:
        text = c.get("text", "").lower()
        matched_trigger = None
        for t in triggers:
            if any(kw.lower() in text for kw in t.get("keywords", [])):
                matched_trigger = t
                break
        if matched_trigger:
            kws = matched_trigger["keywords"]
            print(f"    DISPARARIA para: \"{c.get('text', '')[:60]}\" → keywords: {kws}")
        else:
            print(f"    Sem match: \"{c.get('text', '')[:60]}\"")
    if not comments:
        print("  (Nenhum comentario encontrado para dry-run)")


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

    save_triggers(triggers)
    save_state()
    copy_responder()
    print()

    print("  Instalando agendador...")
    install_launchagent(cadencia)
    print()

    print("  Executando dry-run (simulacao sem envios reais)...")
    dry_run(triggers, token)
    print()

    mark_checkpoint("step_4_comment_responder", "done", f"keywords={len(triggers)} cadencia={cadencia}min")

    print("  [OK] Etapa 4 concluida!")
    print()
    print("  Proximo: python3 setup/setup_dm_kb.py")
    print()


if __name__ == "__main__":
    main()
