#!/usr/bin/env python3
"""
smoke_test_runtime.py — Verifica o ambiente de runtime das automacoes Instagram.

Executa 5 checks que validam o ambiente REAL onde os LaunchAgents rodam,
nao apenas a existencia de arquivos.

Uso:
  python3 scripts/smoke_test_runtime.py
  python3 scripts/smoke_test_runtime.py --verbose
"""

import json
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from lib import (
    IG_ENV_PATH,
    IG_KB_PATH,
    IG_TRIGGERS_PATH,
    INSTAGRAM_DIR,
    PLATFORM,
    load_env_var,
)

VERBOSE = "--verbose" in sys.argv
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


def _fmt(idx, total, label, status, msg):
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ "}.get(status, "  ")
    return f"  [{idx}/{total}] {icon} {label:<38} {msg}"


# ---------------------------------------------------------------------------
# Check 1: lib.py importavel de ~/.operacao-ia/scripts/instagram/
# ---------------------------------------------------------------------------

def check_lib_importable():
    installed_lib = INSTAGRAM_DIR / "lib.py"
    if not installed_lib.exists():
        return FAIL, f"lib.py nao encontrado em {INSTAGRAM_DIR}"
    installed_dir = str(INSTAGRAM_DIR)
    if installed_dir not in sys.path:
        sys.path.insert(0, installed_dir)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("lib_installed", str(installed_lib))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return PASS, f"lib.py importavel de {INSTAGRAM_DIR}"
    except Exception as e:
        return FAIL, f"ImportError: {e}"


# ---------------------------------------------------------------------------
# Check 2: ig_triggers.json schema valido
# ---------------------------------------------------------------------------

def check_triggers_schema():
    if not IG_TRIGGERS_PATH.exists():
        return FAIL, f"ig_triggers.json nao encontrado: {IG_TRIGGERS_PATH}"
    try:
        raw = json.loads(IG_TRIGGERS_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "triggers" in raw:
            return WARN, "formato legado {triggers:[...]} — execute: python3 setup/setup_audit_s5.py --fix"
        if not isinstance(raw, list):
            return FAIL, f"esperado lista, encontrado {type(raw).__name__}"
        if not raw:
            return WARN, "ig_triggers.json vazio (lista vazia)"
        from ig_schemas import validate_triggers
        validate_triggers(raw)
        return PASS, f"{len(raw)} trigger(s) valido(s)"
    except ValueError as e:
        return FAIL, f"schema invalido: {e}"
    except Exception as e:
        return FAIL, f"erro ao ler: {e}"


# ---------------------------------------------------------------------------
# Check 3: ig_kb.json schema valido
# ---------------------------------------------------------------------------

def check_kb_schema():
    if not IG_KB_PATH.exists():
        return WARN, f"ig_kb.json nao encontrado (DM Agent sem base de conhecimento)"
    try:
        raw = json.loads(IG_KB_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return FAIL, f"esperado lista, encontrado {type(raw).__name__}"
        if not raw:
            return WARN, "ig_kb.json vazio"
        from ig_schemas import validate_products
        validate_products(raw)
        return PASS, f"{len(raw)} produto(s) valido(s)"
    except ValueError as e:
        return FAIL, f"schema invalido: {e}"
    except Exception as e:
        return FAIL, f"erro ao ler: {e}"


# ---------------------------------------------------------------------------
# Check 4: LaunchAgents existem e estao loaded
# ---------------------------------------------------------------------------

def check_launchagents_loaded():
    if PLATFORM != "Darwin":
        return WARN, f"plataforma {PLATFORM}: verificacao manual necessaria"

    agents = ["com.zxlab.ig-auto", "com.zxlab.ig-dm"]
    loaded, not_loaded = [], []

    for agent in agents:
        plist = LAUNCH_AGENTS_DIR / f"{agent}.plist"
        if not plist.exists():
            not_loaded.append(f"{agent} (plist nao existe)")
            continue
        try:
            result = subprocess.run(
                ["launchctl", "list", agent],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                loaded.append(agent)
            else:
                not_loaded.append(f"{agent} (nao carregado)")
        except Exception as e:
            not_loaded.append(f"{agent} (erro: {e})")

    if not not_loaded:
        return PASS, f"carregados: {', '.join(loaded)}"
    if loaded:
        return WARN, f"carregados={loaded} | problemas={not_loaded}"
    return FAIL, f"nenhum agent carregado: {not_loaded}"


# ---------------------------------------------------------------------------
# Check 5: Dry-run do script instalado (execucao real no ambiente do LaunchAgent)
# ---------------------------------------------------------------------------

def check_dry_run_installed():
    installed = INSTAGRAM_DIR / "ig_auto_responder.py"
    if not installed.exists():
        return FAIL, f"ig_auto_responder.py nao instalado em {INSTAGRAM_DIR}"

    python_path = shutil.which("python3") or "python3"
    log_path = INSTAGRAM_DIR / "logs" / "ig-auto.log"
    size_before = log_path.stat().st_size if log_path.exists() else 0

    try:
        result = subprocess.run(
            [python_path, str(installed), "--dry-run"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path.home()),
            env=_runtime_env(),
        )
        output = (result.stdout + result.stderr).strip()

        if VERBOSE and output:
            print()
            for line in output.splitlines()[-8:]:
                print(f"       {line}")
            print()

        if result.returncode != 0:
            snippet = output.splitlines()[-1] if output else "(sem output)"
            return FAIL, f"exit {result.returncode}: {snippet[:80]}"

        if log_path.exists() and log_path.stat().st_size > size_before:
            return PASS, "script instalado executou e logou"

        if "Nenhuma palavra-chave" in output or "triggers" in output.lower():
            return WARN, "script rodou mas sem triggers configurados"

        return PASS, "script instalado executou sem erros"
    except subprocess.TimeoutExpired:
        return FAIL, "timeout 30s"
    except Exception as e:
        return FAIL, f"excecao: {e}"


def _runtime_env():
    """Replica o ambiente minimo que o LaunchAgent usa."""
    import os
    env = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
    }
    # Propaga ANTHROPIC_API_KEY se presente
    ak = os.environ.get("ANTHROPIC_API_KEY") or load_env_var(IG_ENV_PATH, "ANTHROPIC_API_KEY")
    if ak:
        env["ANTHROPIC_API_KEY"] = ak
    return env


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS = [
    ("lib.py importavel do runtime dir",    check_lib_importable),
    ("ig_triggers.json schema valido",      check_triggers_schema),
    ("ig_kb.json schema valido",            check_kb_schema),
    ("LaunchAgents loaded (ig-auto+ig-dm)", check_launchagents_loaded),
    ("Dry-run script instalado",            check_dry_run_installed),
]


def main():
    total = len(CHECKS)
    print()
    print("  smoke_test_runtime.py — ig-autoflow")
    print(f"  {total} checks | ambiente real do LaunchAgent")
    if VERBOSE:
        print("  modo: --verbose")
    print()

    results = []
    for idx, (label, fn) in enumerate(CHECKS, start=1):
        try:
            status, msg = fn()
        except Exception as e:
            status, msg = FAIL, f"excecao inesperada: {e}"
        print(_fmt(idx, total, label, status, msg))
        results.append((label, status, msg))

    passed = sum(1 for _, s, _ in results if s == PASS)
    warns = sum(1 for _, s, _ in results if s == WARN)
    fails = sum(1 for _, s, _ in results if s == FAIL)

    print()
    print(f"  Resultado: {passed}/{total} PASS", end="")
    if warns:
        print(f"  |  {warns} WARN", end="")
    if fails:
        print(f"  |  {fails} FAIL", end="")
    print()
    print()

    if fails:
        print("  Falhas detectadas — corrija antes de usar em producao.")
        sys.exit(1)
    elif warns:
        print("  Avisos detectados — sistema funcional mas com configuracoes incompletas.")
    else:
        print("  Tudo OK — ambiente de runtime validado.")
    print()


if __name__ == "__main__":
    main()
