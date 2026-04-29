#!/usr/bin/env python3
"""
Etapa 8 — Auditoria Tecnica S5
Verifica 11 componentes da automacao Instagram e corrige automaticamente onde possivel.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    IG_DM_SESSIONS_PATH,
    IG_ENV_PATH,
    IG_TRIGGERS_PATH,
    INSTAGRAM_DIR,
    PLATFORM,
    ensure_structure,
    load_checkpoint,
    load_config,
    load_env_var,
    mark_checkpoint,
)

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

IG_API_BASE = "https://graph.instagram.com/v22.0"


def _fmt(idx, total, label, status, msg):
    counter = f"[{idx}/{total}]"
    status_tag = f"[{status}]"
    return f"  {counter:<7} {label:<35} {status_tag:<9} {msg}"


def check_claude_cli():
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            return ("OK", version or "instalado")
        return ("AVISO", f"claude retornou codigo {result.returncode}")
    except FileNotFoundError:
        return ("ERRO", "claude nao encontrado no PATH")
    except Exception as e:
        return ("ERRO", str(e))


def check_config_phase():
    try:
        config = load_config()
        phase = config.get("phase_completed", 0)
        if phase >= 4:
            return ("OK", f"phase_completed={phase}")
        return ("AVISO", f"phase_completed={phase} (esperado >= 4)")
    except FileNotFoundError:
        return ("AVISO", "config.json nao encontrado")
    except Exception as e:
        return ("ERRO", str(e))


def check_ig_env():
    if IG_ENV_PATH.exists():
        return ("OK", str(IG_ENV_PATH))
    return ("ERRO", f"instagram.env nao encontrado: {IG_ENV_PATH}")


def check_token_valid():
    import urllib.request
    import urllib.error
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    if not token:
        return ("ERRO", "IG_ACCESS_TOKEN ausente em instagram.env")
    url = f"{IG_API_BASE}/me?access_token={token}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            username = data.get("username", "")
            return ("OK", f"@{username}" if username else "token valido")
    except urllib.error.HTTPError as e:
        return ("ERRO", f"HTTP {e.code} — token pode estar expirado")
    except Exception as e:
        return ("AVISO", f"Falha na verificacao: {e}")


def check_user_id_match():
    import urllib.request
    import urllib.error
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    user_id = load_env_var(IG_ENV_PATH, "IG_USER_ID")
    if not token or not user_id:
        return ("AVISO", "IG_ACCESS_TOKEN ou IG_USER_ID ausentes")
    url = f"{IG_API_BASE}/me?access_token={token}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            api_id = data.get("id", "")
            if api_id == user_id:
                return ("OK", f"IG_USER_ID={user_id} bate com token")
            return ("AVISO", f"IG_USER_ID={user_id} mas token retornou id={api_id}")
    except Exception as e:
        return ("AVISO", f"Nao foi possivel verificar: {e}")


def check_auto_responder():
    script = INSTAGRAM_DIR / "ig_auto_responder.py"
    if script.exists() and script.stat().st_size > 0:
        return ("OK", str(script))
    if script.exists():
        return ("AVISO", "ig_auto_responder.py existe mas esta vazio")
    return ("ERRO", f"ig_auto_responder.py nao encontrado em {INSTAGRAM_DIR}")


def check_dm_agent():
    script = INSTAGRAM_DIR / "ig_dm_agent.py"
    if script.exists() and script.stat().st_size > 0:
        return ("OK", str(script))
    if script.exists():
        return ("AVISO", "ig_dm_agent.py existe mas esta vazio")
    return ("ERRO", f"ig_dm_agent.py nao encontrado em {INSTAGRAM_DIR}")


def check_triggers():
    if not IG_TRIGGERS_PATH.exists():
        return ("ERRO", f"ig_triggers.json nao encontrado: {IG_TRIGGERS_PATH}")
    try:
        data = json.loads(IG_TRIGGERS_PATH.read_text(encoding="utf-8"))
        triggers = data.get("triggers", [])
        if len(triggers) >= 1:
            return ("OK", f"{len(triggers)} keyword(s) cadastrada(s)")
        return ("AVISO", "ig_triggers.json existe mas sem keywords")
    except Exception as e:
        return ("ERRO", f"ig_triggers.json invalido: {e}")


def check_omniroute():
    import urllib.request
    import urllib.error
    dm_config_path = INSTAGRAM_DIR / "dm_agent_config.json"
    url = "http://localhost:8765"
    if dm_config_path.exists():
        try:
            cfg = json.loads(dm_config_path.read_text(encoding="utf-8"))
            url = cfg.get("omniroute_url", url)
        except Exception:
            pass
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return ("OK", f"respondendo em {url}")
        return ("AVISO", f"resposta inesperada em {url}")
    except Exception:
        return ("AVISO", f"OmniRoute nao respondeu em {url}")


def check_dm_sessions():
    if IG_DM_SESSIONS_PATH.exists():
        return ("OK", str(IG_DM_SESSIONS_PATH))
    try:
        IG_DM_SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        IG_DM_SESSIONS_PATH.touch()
        return ("OK", f"criado agora: {IG_DM_SESSIONS_PATH}")
    except Exception as e:
        return ("AVISO", f"nao foi possivel criar: {e}")


def check_launchagents():
    if PLATFORM == "Darwin":
        ig_auto = LAUNCH_AGENTS_DIR / "com.zxlab.ig-auto.plist"
        ig_dm = LAUNCH_AGENTS_DIR / "com.zxlab.ig-dm.plist"
        loaded = []
        missing = []
        for plist in [ig_auto, ig_dm]:
            if plist.exists():
                try:
                    result = subprocess.run(
                        ["launchctl", "list", plist.stem.replace(".plist", "")],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        loaded.append(plist.name)
                    else:
                        missing.append(f"{plist.name} (nao carregado)")
                except Exception:
                    missing.append(f"{plist.name} (erro ao verificar)")
            else:
                missing.append(f"{plist.name} (nao encontrado)")

        if not missing:
            return ("OK", f"carregados: {', '.join(loaded)}")
        if loaded:
            return ("AVISO", f"carregados={loaded} | problemas={missing}")
        return ("AVISO", f"LaunchAgents nao encontrados: {missing}")
    elif PLATFORM == "Linux":
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if "ig_auto_responder" in result.stdout and "ig_dm_agent" in result.stdout:
            return ("OK", "cron entries presentes")
        return ("AVISO", "cron entries nao encontrados — executar etapas 4 e 6")
    else:
        return ("AVISO", f"Plataforma {PLATFORM} — verificacao manual necessaria")


CHECKS = [
    ("Claude Code CLI",               check_claude_cli),
    ("Config.json phase >= 4",        check_config_phase),
    ("instagram.env existe",          check_ig_env),
    ("IG_ACCESS_TOKEN valido",        check_token_valid),
    ("IG_USER_ID bate com token",     check_user_id_match),
    ("ig_auto_responder.py",          check_auto_responder),
    ("ig_dm_agent.py",                check_dm_agent),
    ("ig_triggers.json >= 1 keyword", check_triggers),
    ("OmniRoute localhost:8765",      check_omniroute),
    ("ig_dm_sessions.sqlite",         check_dm_sessions),
    ("LaunchAgents ig-auto + ig-dm",  check_launchagents),
]

TOTAL = len(CHECKS)


def run_all_checks():
    results = []
    for idx, (label, fn) in enumerate(CHECKS, start=1):
        try:
            status, msg = fn()
        except Exception as e:
            status, msg = "ERRO", f"excecao inesperada: {e}"
        line = _fmt(idx, TOTAL, label, status, msg)
        print(line)
        results.append((label, status, msg))
    return results


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [████████░░] Etapa 8 de 10")
    print()
    print("  Etapa 8 — Auditoria Tecnica")
    print()
    print(f"  Verificando {TOTAL} componentes da automacao Instagram.")
    print("  Fixes automaticos serao aplicados onde possivel.")
    print()

    ensure_structure()

    results = run_all_checks()

    ok = sum(1 for _, status, _ in results if status == "OK")
    avisos = sum(1 for _, status, _ in results if status == "AVISO")
    erros = sum(1 for _, status, _ in results if status == "ERRO")

    print()
    print(f"  Resultado: {ok}/{TOTAL} checks passaram", end="")
    if avisos:
        print(f"  |  {avisos} aviso(s)", end="")
    if erros:
        print(f"  |  {erros} erro(s)", end="")
    print()
    print()

    pendentes = [(label, status, msg) for label, status, msg in results if status != "OK"]
    if pendentes:
        print("  Itens que precisam de atencao:")
        for label, status, msg in pendentes:
            print(f"    [{status}] {label}: {msg}")
        print()

    detail = f"{ok}/{TOTAL} checks passaram"
    mark_checkpoint("step_8_audit_s5", "done", f"score={ok}/{TOTAL}")

    print("  [OK] Etapa 8 concluida — Auditoria Tecnica finalizada!")
    print()
    print("  Proximo: python3 setup/setup_teste_pratico.py")
    print()


if __name__ == "__main__":
    main()
