#!/usr/bin/env python3
"""
Etapa 8 — Auditoria Tecnica S5
Verifica componentes da automacao Instagram e corrige automaticamente onde possivel.

Uso:
  python3 setup/setup_audit_s5.py              # auditoria normal
  python3 setup/setup_audit_s5.py --fix        # corrige ig_triggers.json e ig_kb.json
  python3 setup/setup_audit_s5.py --with-runtime  # inclui check end-to-end
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
    IG_DM_SESSIONS_PATH,
    IG_ENV_PATH,
    IG_KB_PATH,
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

FLAG_FIX = "--fix" in sys.argv
FLAG_RUNTIME = "--with-runtime" in sys.argv


def _fmt(idx, total, label, status, msg):
    counter = f"[{idx}/{total}]"
    status_tag = f"[{status}]"
    return f"  {counter:<7} {label:<40} {status_tag:<9} {msg}"


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_claude_cli():
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            return "OK", version or "instalado"
        return "AVISO", f"claude retornou codigo {result.returncode}"
    except FileNotFoundError:
        return "ERRO", "claude nao encontrado no PATH"
    except Exception as e:
        return "ERRO", str(e)


def check_config_phase():
    try:
        config = load_config()
        phase = config.get("phase_completed", 0)
        if phase >= 4:
            return "OK", f"phase_completed={phase}"
        return "AVISO", f"phase_completed={phase} (esperado >= 4) — para avançar: jq '.phase_completed = 4' ~/.operacao-ia/config/config.json | sponge ~/.operacao-ia/config/config.json"
    except FileNotFoundError:
        return "AVISO", "config.json nao encontrado"
    except Exception as e:
        return "ERRO", str(e)


def check_ig_env():
    if IG_ENV_PATH.exists():
        return "OK", str(IG_ENV_PATH)
    return "ERRO", f"instagram.env nao encontrado: {IG_ENV_PATH}"


def check_token_valid():
    import urllib.request, urllib.error
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    if not token:
        return "ERRO", "IG_ACCESS_TOKEN ausente em instagram.env"
    url = f"{IG_API_BASE}/me?access_token={token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            username = data.get("username", "")
            return "OK", f"@{username}" if username else "token valido"
    except urllib.error.HTTPError as e:
        return "ERRO", f"HTTP {e.code} — token pode estar expirado"
    except Exception as e:
        return "AVISO", f"Falha na verificacao: {e}"


def check_user_id_match():
    import urllib.request, urllib.error
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    user_id = load_env_var(IG_ENV_PATH, "IG_USER_ID")
    if not token or not user_id:
        return "AVISO", "IG_ACCESS_TOKEN ou IG_USER_ID ausentes"
    url = f"{IG_API_BASE}/me?access_token={token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            api_id = data.get("id", "")
            if api_id == user_id:
                return "OK", f"IG_USER_ID={user_id} bate com token"
            return "AVISO", f"IG_USER_ID={user_id} mas token retornou id={api_id}"
    except Exception as e:
        return "AVISO", f"Nao foi possivel verificar: {e}"


def check_auto_responder():
    script = INSTAGRAM_DIR / "ig_auto_responder.py"
    if script.exists() and script.stat().st_size > 0:
        return "OK", str(script)
    if script.exists():
        return "AVISO", "ig_auto_responder.py existe mas esta vazio"
    return "ERRO", f"ig_auto_responder.py nao encontrado em {INSTAGRAM_DIR}"


def check_dm_agent():
    script = INSTAGRAM_DIR / "ig_dm_agent.py"
    if script.exists() and script.stat().st_size > 0:
        return "OK", str(script)
    if script.exists():
        return "AVISO", "ig_dm_agent.py existe mas esta vazio"
    return "ERRO", f"ig_dm_agent.py nao encontrado em {INSTAGRAM_DIR}"


def check_triggers():
    """
    ig_triggers.json deve ser uma lista (nao um objeto com chave 'triggers').
    Se --fix, reescreve no formato canonico.
    """
    if not IG_TRIGGERS_PATH.exists():
        return "ERRO", f"ig_triggers.json nao encontrado: {IG_TRIGGERS_PATH}"
    try:
        raw = json.loads(IG_TRIGGERS_PATH.read_text(encoding="utf-8"))

        # formato legado: {"triggers": [...]}
        if isinstance(raw, dict) and "triggers" in raw:
            if FLAG_FIX:
                fixed = raw["triggers"]
                IG_TRIGGERS_PATH.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding="utf-8")
                return "OK", f"[CORRIGIDO] formato legado migrado — {len(fixed)} trigger(s)"
            return "AVISO", "formato legado {triggers:[...]} — execute com --fix para corrigir"

        if not isinstance(raw, list):
            return "ERRO", f"ig_triggers.json invalido: esperado lista, encontrado {type(raw).__name__}"

        from ig_schemas import validate_triggers
        triggers = validate_triggers(raw)
        return "OK", f"{len(triggers)} keyword(s) cadastrada(s)"
    except Exception as e:
        return "ERRO", f"ig_triggers.json invalido: {e}"


def check_anthropic_key():
    """Verifica ANTHROPIC_API_KEY no ambiente ou no instagram.env."""
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "") or load_env_var(IG_ENV_PATH, "ANTHROPIC_API_KEY") or ""
    if not key:
        return "ERRO", "ANTHROPIC_API_KEY nao encontrada (ambiente nem instagram.env)"
    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    return "OK", f"chave presente: {masked}"


def check_dm_sessions():
    if IG_DM_SESSIONS_PATH.exists():
        return "OK", str(IG_DM_SESSIONS_PATH)
    try:
        IG_DM_SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        IG_DM_SESSIONS_PATH.touch()
        return "OK", f"criado agora: {IG_DM_SESSIONS_PATH}"
    except Exception as e:
        return "AVISO", f"nao foi possivel criar: {e}"


def check_launchagents():
    if PLATFORM == "Darwin":
        ig_auto = LAUNCH_AGENTS_DIR / "com.zxlab.ig-auto.plist"
        ig_dm = LAUNCH_AGENTS_DIR / "com.zxlab.ig-dm.plist"
        loaded, missing = [], []
        for plist in [ig_auto, ig_dm]:
            if plist.exists():
                try:
                    result = subprocess.run(
                        ["launchctl", "list", plist.stem],
                        capture_output=True, text=True, timeout=5,
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
            return "OK", f"carregados: {', '.join(loaded)}"
        if loaded:
            return "AVISO", f"carregados={loaded} | problemas={missing}"
        return "AVISO", f"LaunchAgents nao encontrados: {missing}"
    elif PLATFORM == "Linux":
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if "ig_auto_responder" in result.stdout and "ig_dm_agent" in result.stdout:
            return "OK", "cron entries presentes"
        return "AVISO", "cron entries nao encontrados — execute etapas 4 e 6"
    else:
        return "AVISO", f"Plataforma {PLATFORM} — verificacao manual necessaria"


def check_disparo_end_to_end():
    """
    Roda o script INSTALADO em --dry-run e verifica se apareceu entrada nova no log.
    So executado com --with-runtime.
    """
    import shutil
    installed = INSTAGRAM_DIR / "ig_auto_responder.py"
    if not installed.exists():
        return "ERRO", "ig_auto_responder.py nao instalado"

    log_path = INSTAGRAM_DIR / "logs" / "ig-auto.log"
    size_before = log_path.stat().st_size if log_path.exists() else 0

    python_path = shutil.which("python3") or "python3"
    try:
        result = subprocess.run(
            [python_path, str(installed), "--dry-run"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path.home()),
        )
        output = (result.stdout + result.stderr).strip()
        if log_path.exists() and log_path.stat().st_size > size_before:
            return "OK", "script instalado rodou e logou"
        if result.returncode == 0:
            return "AVISO", "script rodou mas nao gerou log (token invalido ou sem posts?)"
        return "ERRO", f"script retornou codigo {result.returncode}: {output[:100]}"
    except subprocess.TimeoutExpired:
        return "ERRO", "dry-run excedeu 30s"
    except Exception as e:
        return "ERRO", f"excecao: {e}"


# ---------------------------------------------------------------------------
# Lista de checks
# ---------------------------------------------------------------------------

CHECKS_BASE = [
    ("Claude Code CLI",                check_claude_cli),
    ("Config.json phase >= 4",         check_config_phase),
    ("instagram.env existe",           check_ig_env),
    ("IG_ACCESS_TOKEN valido",         check_token_valid),
    ("IG_USER_ID bate com token",      check_user_id_match),
    ("ig_auto_responder.py",           check_auto_responder),
    ("ig_dm_agent.py",                 check_dm_agent),
    ("ig_triggers.json >= 1 keyword",  check_triggers),
    ("ANTHROPIC_API_KEY",              check_anthropic_key),
    ("ig_dm_sessions.sqlite",          check_dm_sessions),
    ("LaunchAgents ig-auto + ig-dm",   check_launchagents),
]

CHECKS_RUNTIME = [
    ("Disparo end-to-end (dry-run)",   check_disparo_end_to_end),
]


def run_all_checks(checks):
    results = []
    total = len(checks)
    for idx, (label, fn) in enumerate(checks, start=1):
        try:
            status, msg = fn()
        except Exception as e:
            status, msg = "ERRO", f"excecao inesperada: {e}"
        line = _fmt(idx, total, label, status, msg)
        print(line)
        results.append((label, status, msg))
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
    print("  [████████░░] Etapa 8 de 10")
    print()
    print("  Etapa 8 — Auditoria Tecnica")

    flags = []
    if FLAG_FIX:
        flags.append("--fix: corrigindo schemas automaticamente")
    if FLAG_RUNTIME:
        flags.append("--with-runtime: incluindo check end-to-end")
    if flags:
        print(f"  Flags: {' | '.join(flags)}")
    print()

    ensure_structure()

    checks = CHECKS_BASE + (CHECKS_RUNTIME if FLAG_RUNTIME else [])
    total = len(checks)
    print(f"  Verificando {total} componentes da automacao Instagram.")
    print()

    results = run_all_checks(checks)

    ok = sum(1 for _, s, _ in results if s == "OK")
    avisos = sum(1 for _, s, _ in results if s == "AVISO")
    erros = sum(1 for _, s, _ in results if s == "ERRO")

    print()
    print(f"  Resultado: {ok}/{total} checks passaram", end="")
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
        if any(s == "AVISO" for _, s, _ in pendentes) and not FLAG_FIX:
            print()
            print("  Dica: execute com --fix para corrigir schemas automaticamente:")
            print("    python3 setup/setup_audit_s5.py --fix")
        print()

    if not FLAG_RUNTIME:
        print("  Dica: para teste end-to-end real:")
        print("    python3 setup/setup_audit_s5.py --with-runtime")
        print()

    mark_checkpoint("step_8_audit_s5", "done", f"score={ok}/{total}")

    print("  [OK] Etapa 8 concluida — Auditoria Tecnica finalizada!")
    print()
    print("  Proximo: python3 setup/setup_teste_pratico.py")
    print()


if __name__ == "__main__":
    main()
