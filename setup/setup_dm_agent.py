#!/usr/bin/env python3
"""
Etapa 6 — DM Agent
Configurar Anthropic API, Evolution (opcional) e instalar agentes de DM + token refresh.
OmniRoute removido — aluno ZX Control ja tem ANTHROPIC_API_KEY (usa Claude Code).
"""

import json
import os
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
    INSTAGRAM_DIR,
    PLATFORM,
    install_schtask,
    load_env_var,
    mark_checkpoint,
    run_schtask_and_verify,
)

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
TEMPLATES_DIR = ROOT_DIR / "templates"
IG_DM_AGENT_SRC = ROOT_DIR / "scripts" / "ig_dm_agent.py"
IG_TOKEN_REFRESH_SRC = ROOT_DIR / "scripts" / "ig_token_refresh.py"
LIB_SRC = ROOT_DIR / "scripts" / "lib.py"
IG_SCHEMAS_SRC = ROOT_DIR / "scripts" / "ig_schemas.py"


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


# ---------------------------------------------------------------------------
# Verificacao Anthropic
# ---------------------------------------------------------------------------

def check_anthropic_key(api_key=None):
    """Faz uma chamada de teste real para garantir que a chave funciona."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return False, "ANTHROPIC_API_KEY nao encontrada no ambiente"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True, f"OK — modelo: claude-haiku-4-5-20251001"
    except Exception as e:
        return False, f"Erro na chamada de teste: {e}"


# ---------------------------------------------------------------------------
# Salvar config
# ---------------------------------------------------------------------------

def save_dm_config(evo_url, evo_instance, whatsapp_num, cadencia):
    config_path = INSTAGRAM_DIR / "dm_agent_config.json"
    INSTAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "evolution_url": evo_url,
        "evolution_instance": evo_instance,
        "whatsapp_escalation_number": whatsapp_num,
        "cadencia_minutos": cadencia,
    }
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  [OK] dm_agent_config.json salvo.")


def append_to_env(key, value):
    lines = []
    if IG_ENV_PATH.exists():
        # Backup do .env antes de modificar — recover manual se algo der errado
        try:
            IG_ENV_PATH.with_suffix(IG_ENV_PATH.suffix + ".bak").write_text(
                IG_ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8"
            )
        except Exception:
            pass
        lines = IG_ENV_PATH.read_text(encoding="utf-8").splitlines()
    existing_keys = {l.split("=")[0].strip() for l in lines if "=" in l}
    if key in existing_keys:
        lines = [f"{key}={value}" if l.startswith(key + "=") else l for l in lines]
    else:
        lines.append(f"{key}={value}")
    IG_ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(IG_ENV_PATH, 0o600)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Copiar scripts para runtime dir
# ---------------------------------------------------------------------------

def copy_scripts():
    dest_dir = INSTAGRAM_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in [IG_DM_AGENT_SRC, IG_TOKEN_REFRESH_SRC, LIB_SRC, IG_SCHEMAS_SRC]:
        if src.exists():
            shutil.copy2(str(src), str(dest_dir / src.name))
            print(f"  [OK] {src.name} copiado para {dest_dir}")
        else:
            print(f"  [AVISO] {src.name} nao encontrado em scripts/.")


# ---------------------------------------------------------------------------
# LaunchAgents
# ---------------------------------------------------------------------------

def _kickstart_and_verify(label, log_path, timeout=8):
    size_before = Path(log_path).stat().st_size if Path(log_path).exists() else 0
    try:
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


def _write_plist(plist_name, python_path, script_path, interval, log_path, env_vars=None):
    env_block = ""
    if env_vars:
        pairs = "\n".join(
            f"        <key>{k}</key>\n        <string>{v}</string>"
            for k, v in env_vars.items()
        )
        env_block = f"""    <key>EnvironmentVariables</key>
    <dict>
{pairs}
    </dict>
"""
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
{env_block}    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
    dest = LAUNCH_AGENTS_DIR / plist_name
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def _write_token_plist(python_path, script_path, log_path):
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.zxlab.ig-token</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
    dest = LAUNCH_AGENTS_DIR / "com.zxlab.ig-token.plist"
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def install_launchagents(cadencia, anthropic_key):
    # sys.executable e sempre o interpretador correto; "python3" nao existe no Windows
    python_path = sys.executable
    logs_dir = INSTAGRAM_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    dm_agent_path = INSTAGRAM_DIR / "ig_dm_agent.py"
    dm_log = logs_dir / "ig-dm.log"
    token_refresher_path = INSTAGRAM_DIR / "ig_token_refresh.py"
    token_log = logs_dir / "ig-token.log"
    interval_dm = cadencia * 60

    results = {}

    if PLATFORM == "Darwin":
        # DM Agent
        # NOTA SEGURANÇA: ANTHROPIC_API_KEY vai em plain text no plist (~/Library/LaunchAgents/).
        # Plist tem permissão padrão 644. Para reduzir exposição, chmod 600 abaixo.
        # TimeMachine sem criptografia pode replicar o plist — recomendar FileVault no setup.
        env_vars = {}
        if anthropic_key:
            env_vars["ANTHROPIC_API_KEY"] = anthropic_key
        plist_dm = _write_plist(
            "com.zxlab.ig-dm.plist", python_path, str(dm_agent_path),
            interval_dm, str(dm_log), env_vars=env_vars or None,
        )
        try:
            os.chmod(plist_dm, 0o600)
        except Exception:
            pass
        try:
            subprocess.run(
                ["launchctl", "unload", str(plist_dm)],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["launchctl", "load", str(plist_dm)],
                check=True, capture_output=True, timeout=10,
            )
            print(f"  [OK] LaunchAgent DM instalado: {plist_dm}")
        except subprocess.CalledProcessError as e:
            print(f"  [AVISO] launchctl load ig-dm falhou: {e}")

        print("  Verificando 1a execucao do DM agent...")
        ok_dm, detail_dm = _kickstart_and_verify("com.zxlab.ig-dm", dm_log)
        if ok_dm:
            print("  [OK] 1a execucao do DM agent: OK")
        else:
            print(f"  [AVISO] DM agent instalado mas nao logou ({detail_dm}).")
        results["dm"] = ok_dm

        # Token Refresh — apenas se ig_token_refresh.py existir
        if token_refresher_path.exists():
            plist_token = _write_token_plist(python_path, str(token_refresher_path), str(token_log))
            try:
                os.chmod(plist_token, 0o600)
            except Exception:
                pass
            try:
                subprocess.run(
                    ["launchctl", "unload", str(plist_token)],
                    capture_output=True, timeout=10,
                )
                subprocess.run(
                    ["launchctl", "load", str(plist_token)],
                    check=True, capture_output=True, timeout=10,
                )
                print(f"  [OK] LaunchAgent Token instalado: {plist_token}")
            except subprocess.CalledProcessError as e:
                print(f"  [AVISO] launchctl load ig-token falhou: {e}")

            print("  Verificando 1a execucao do Token Refresh (esperado: exit 0 silencioso)...")
            ok_token, detail_token = _kickstart_and_verify("com.zxlab.ig-token", token_log, timeout=10)
            if ok_token:
                print("  [OK] Token Refresh executado.")
            else:
                print(f"  [AVISO] Token Refresh nao logou ({detail_token}) — normal se token < 24h.")
            results["token"] = ok_token
        else:
            print("  [AVISO] ig_token_refresh.py nao encontrado, LaunchAgent de token nao instalado.")

    elif PLATFORM == "Linux":
        print(f"  [INFO] Linux: adicione ao cron manualmente:")
        print(f"    */{cadencia} * * * * {python_path} {dm_agent_path}")
        print(f"    0 2 * * * {python_path} {token_refresher_path}")
        results["dm"] = True
    elif PLATFORM == "Windows":
        # DM Agent (a chave de IA e lida do instagram.env pelo proprio agente)
        ok_dm, detail_dm = install_schtask("ZXLab-IG-DM", dm_agent_path, every_minutes=cadencia)
        if ok_dm:
            print(f"  [OK] Tarefa agendada criada: ZXLab-IG-DM (a cada {cadencia} min, via pythonw)")
            print("  Verificando 1a execucao do DM agent...")
            ran, run_detail = run_schtask_and_verify("ZXLab-IG-DM", dm_log)
            if ran:
                print("  [OK] 1a execucao do DM agent: OK")
            else:
                print(f"  [AVISO] DM agent instalado mas nao logou ({run_detail}).")
            results["dm"] = ran
        else:
            print(f"  [AVISO] schtasks ig-dm falhou: {detail_dm}")
            results["dm"] = False

        # Token Refresh diario
        if token_refresher_path.exists():
            ok_token, detail_token = install_schtask("ZXLab-IG-Token", token_refresher_path, daily_time="03:00")
            if ok_token:
                print("  [OK] Tarefa agendada criada: ZXLab-IG-Token (diaria as 03:00)")
            else:
                print(f"  [AVISO] schtasks ig-token falhou: {detail_token}")
            results["token"] = ok_token
        else:
            print("  [AVISO] ig_token_refresh.py nao encontrado, tarefa de token nao instalada.")
    else:
        print(f"  [AVISO] Plataforma {PLATFORM}: instale agendadores manualmente.")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [██████░░░░] Etapa 6 de 10")
    print()
    print("  Etapa 6 — DM Agent (Anthropic SDK + LaunchAgents)")
    print()

    # 6a: Verificar ANTHROPIC_API_KEY
    print("  6a — Verificando ANTHROPIC_API_KEY...")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "") or load_env_var(IG_ENV_PATH, "ANTHROPIC_API_KEY") or ""

    if not anthropic_key:
        print("  Chave nao encontrada no ambiente. Cole sua ANTHROPIC_API_KEY:")
        anthropic_key = ask("ANTHROPIC_API_KEY", secret=True)
        if not anthropic_key:
            print("  [ERRO] ANTHROPIC_API_KEY e obrigatoria para o DM Agent.")
            sys.exit(1)

    print("  Testando ANTHROPIC_API_KEY...")
    ok, detail = check_anthropic_key(anthropic_key)
    if not ok:
        print(f"  [ERRO] Anthropic nao respondeu: {detail}")
        print("  Corrija a chave e execute esta etapa novamente.")
        mark_checkpoint("step_6_dm_agent", "partial", f"anthropic_key_invalid: {detail}")
        sys.exit(1)
    print(f"  [OK] Anthropic: {detail}")
    append_to_env("ANTHROPIC_API_KEY", anthropic_key)
    print()

    # 6b: Evolution (opcional)
    print("  6b — Evolution API para escalacao WhatsApp (opcional):")
    tem_evolution = ask("Voce tem Evolution API configurada? (s/N)", default="N").lower()
    evo_url, evo_instance, whatsapp_num = "", "", ""
    if tem_evolution in ("s", "sim", "y", "yes"):
        evo_url = ask("URL da Evolution API", default=load_env_var(IG_ENV_PATH, "EVOLUTION_BASE") or "")
        evo_instance = ask("Nome da instancia WhatsApp", default=load_env_var(IG_ENV_PATH, "EVOLUTION_INSTANCE") or "")
        whatsapp_num = ask("Seu numero WhatsApp com DDI (ex: 5585999999999)", default=load_env_var(IG_ENV_PATH, "USER_WHATSAPP_NUMBER") or "")
        if evo_url:
            append_to_env("EVOLUTION_BASE", evo_url)
        if evo_instance:
            append_to_env("EVOLUTION_INSTANCE", evo_instance)
        if whatsapp_num:
            append_to_env("USER_WHATSAPP_NUMBER", whatsapp_num)
        print("  [OK] Evolution configurada.")
    else:
        print("  [INFO] Sem Evolution — escalacao via DM direta (link WhatsApp no dm_text do trigger).")
    print()

    # 6c: Cadencia DM
    print("  6c — Cadencia do DM Agent:")
    cadencia_str = ask("Cadencia em minutos (2-30)", default="5")
    try:
        cadencia = int(cadencia_str)
        cadencia = max(2, min(30, cadencia))
    except ValueError:
        cadencia = 5
    print(f"  [OK] Cadencia: {cadencia} minutos.")
    print()

    # 6d: Copiar scripts
    print("  6d — Instalando scripts de runtime...")
    copy_scripts()
    print()

    # Salvar config
    save_dm_config(evo_url, evo_instance, whatsapp_num, cadencia)
    print()

    # 6e: Instalar LaunchAgents
    print("  6e — Instalando LaunchAgents...")
    agent_results = install_launchagents(cadencia, anthropic_key)
    print()

    dm_ok = agent_results.get("dm", False)

    if dm_ok:
        status = "done"
        detail = f"anthropic=ok cadencia={cadencia}min"
    else:
        status = "partial"
        detail = f"anthropic=ok cadencia={cadencia}min dm_agent_nao_confirmado"

    mark_checkpoint("step_6_dm_agent", status, detail)

    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║  Comandos uteis apos esta etapa:                     ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    if PLATFORM == "Windows":
        print('  Forcar DM agent agora:  schtasks /Run /TN "ZXLab-IG-DM"')
        print(f"  Ver log DM:             Get-Content \"{INSTAGRAM_DIR}\\logs\\ig-dm.log\" -Tail 20 -Wait")
    else:
        uid = os.getuid() if PLATFORM == "Darwin" else "$(id -u)"
        print(f"  Forcar DM agent agora:  launchctl kickstart -k gui/{uid}/com.zxlab.ig-dm")
        print(f"  Ver log DM:             tail -f {INSTAGRAM_DIR}/logs/ig-dm.log")
    print()
    print("  [OK] Etapa 6 concluida!")
    print()
    print("  Proximo: python3 setup/setup_mission_update_s5.py")
    print()


if __name__ == "__main__":
    main()
