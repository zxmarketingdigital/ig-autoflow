#!/usr/bin/env python3
"""
Etapa 6 — DM Agent
Configurar OmniRoute, Evolution API e instalar agentes de DM + token refresh.
"""

import json
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    IG_ENV_PATH,
    INSTAGRAM_DIR,
    PLATFORM,
    load_env_var,
    mark_checkpoint,
)

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
TEMPLATES_DIR = ROOT_DIR / "templates"
IG_DM_AGENT_SRC = ROOT_DIR / "scripts" / "ig_dm_agent.py"


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


def check_omniroute(url):
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def try_install_omniroute():
    try:
        import importlib.util
        if importlib.util.find_spec("omniroute_check") is not None:
            import omniroute_check
            omniroute_check.check_or_install()
            return True
    except Exception as e:
        print(f"  [AVISO] omniroute_check nao disponivel: {e}")
    return False


def save_dm_config(omniroute_url, model_main, model_fallback, evo_url, evo_instance, whatsapp_num, cadencia):
    config_path = INSTAGRAM_DIR / "dm_agent_config.json"
    INSTAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "omniroute_url": omniroute_url,
        "model_main": model_main,
        "model_fallback": model_fallback,
        "evolution_url": evo_url,
        "evolution_instance": evo_instance,
        "whatsapp_escalation_number": whatsapp_num,
        "cadencia_minutos": cadencia,
    }
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] dm_agent_config.json salvo.")


def append_to_env(key, value):
    lines = []
    if IG_ENV_PATH.exists():
        lines = IG_ENV_PATH.read_text(encoding="utf-8").splitlines()
    existing_keys = {l.split("=")[0].strip() for l in lines if "=" in l}
    if key in existing_keys:
        lines = [f"{key}={value}" if l.startswith(key + "=") else l for l in lines]
    else:
        lines.append(f"{key}={value}")
    IG_ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_dm_agent():
    dest = INSTAGRAM_DIR / "ig_dm_agent.py"
    if IG_DM_AGENT_SRC.exists():
        shutil.copy2(str(IG_DM_AGENT_SRC), str(dest))
        print(f"  [OK] ig_dm_agent.py copiado para {INSTAGRAM_DIR}")
    else:
        dest.touch()
        print(f"  [AVISO] ig_dm_agent.py nao encontrado em scripts/. Arquivo vazio criado.")


def _write_plist(plist_name, python_path, script_path, interval, log_path):
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_name.replace('.plist', '')}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
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
    dest = LAUNCH_AGENTS_DIR / plist_name
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def install_launchagents(cadencia):
    python_path = shutil.which("python3") or "python3"
    logs_dir = INSTAGRAM_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    dm_agent_path = INSTAGRAM_DIR / "ig_dm_agent.py"
    dm_log = logs_dir / "ig-dm.log"

    token_refresher_path = INSTAGRAM_DIR / "ig_token_refresh.py"
    token_log = logs_dir / "ig-token.log"

    interval_dm = cadencia * 60
    interval_token = 86400  # diario

    if PLATFORM == "Darwin":
        plist_dm = _write_plist("com.zxlab.ig-dm.plist", python_path, str(dm_agent_path), interval_dm, str(dm_log))
        try:
            subprocess.run(["launchctl", "unload", str(plist_dm)], capture_output=True)
            subprocess.run(["launchctl", "load", str(plist_dm)], check=True, capture_output=True)
            print(f"  [OK] LaunchAgent DM instalado: {plist_dm}")
        except subprocess.CalledProcessError as e:
            print(f"  [AVISO] launchctl load ig-dm falhou: {e}")

        plist_token = _write_plist("com.zxlab.ig-token.plist", python_path, str(token_refresher_path), interval_token, str(token_log))
        try:
            subprocess.run(["launchctl", "unload", str(plist_token)], capture_output=True)
            subprocess.run(["launchctl", "load", str(plist_token)], check=True, capture_output=True)
            print(f"  [OK] LaunchAgent Token instalado: {plist_token}")
        except subprocess.CalledProcessError as e:
            print(f"  [AVISO] launchctl load ig-token falhou: {e}")

    elif PLATFORM == "Linux":
        print(f"  [INFO] Linux: adicione ao cron manualmente:")
        print(f"    */{cadencia} * * * * {python_path} {dm_agent_path}")
        print(f"    0 2 * * * {python_path} {token_refresher_path}")
    else:
        print(f"  [AVISO] Plataforma {PLATFORM}: instale agendadores manualmente.")


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [██████░░░░] Etapa 6 de 10")
    print()
    print("  Etapa 6 — DM Agent (OmniRoute + Evolution + LaunchAgents)")
    print()

    # 6a: Verifica OmniRoute
    print("  6a — Verificando OmniRoute...")
    omniroute_found = try_install_omniroute()
    if not omniroute_found:
        print("  (OmniRoute sera verificado pela URL na proxima etapa)")
    print()

    # 6b: Credenciais OmniRoute
    print("  6b — Configurar OmniRoute:")
    omniroute_url = ask("URL do OmniRoute", default="http://localhost:8765")
    model_main = ask("Modelo principal", default="gpt-4o-mini")
    model_fallback = ask("Modelo fallback", default="gemini-2.0-flash")

    print()
    print("  Testando conexao com OmniRoute...")
    if check_omniroute(omniroute_url):
        print(f"  [OK] OmniRoute respondendo em {omniroute_url}")
    else:
        print(f"  [AVISO] OmniRoute nao respondeu em {omniroute_url}")
        print("  Certifique-se de que o OmniRoute esta rodando antes de usar o agente.")
    print()

    # 6c: Evolution para escalacao
    print("  6c — Configurar Evolution API (escalacao WhatsApp):")
    evo_url = ask("URL da Evolution API")
    evo_instance = ask("Nome da instancia WhatsApp")
    whatsapp_num = ask("Seu numero WhatsApp com DDI (ex: 5585999999999)")
    print()

    # 6d: Cadencia DM
    print("  6d — Cadencia do DM Agent:")
    cadencia_str = ask("Cadencia em minutos (1-10)", default="2")
    try:
        cadencia = int(cadencia_str)
        cadencia = max(1, min(10, cadencia))
    except ValueError:
        cadencia = 2
    print(f"  [OK] Cadencia: {cadencia} minutos.")
    print()

    # 6e: Instalar ig_dm_agent.py
    print("  6e — Instalando ig_dm_agent.py...")
    copy_dm_agent()
    print()

    # Salvar config
    save_dm_config(omniroute_url, model_main, model_fallback, evo_url, evo_instance, whatsapp_num, cadencia)

    # Salvar credenciais Evolution no .env
    append_to_env("EVOLUTION_URL", evo_url)
    append_to_env("EVOLUTION_INSTANCE", evo_instance)
    append_to_env("WHATSAPP_ESCALATION_NUMBER", whatsapp_num)
    print("  [OK] Credenciais Evolution salvas em instagram.env.")
    print()

    # 6f: Instalar LaunchAgents
    print("  6f — Instalando LaunchAgents...")
    install_launchagents(cadencia)
    print()

    mark_checkpoint("step_6_dm_agent", "done", f"model={model_main} cadencia={cadencia}min")

    print("  [OK] Etapa 6 concluida!")
    print()
    print("  Proximo: python3 setup/setup_mission_update_s5.py")
    print()


if __name__ == "__main__":
    main()
