#!/usr/bin/env python3
"""Verifica se o OmniRoute esta instalado e respondendo. Oferece instalar se ausente."""

import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


OMNIROUTE_REPO = "https://github.com/zxmarketingdigital/omniroute.git"
OMNIROUTE_DEFAULT_URL = "http://localhost:8765"
OMNIROUTE_DIR = Path.home() / ".omniroute"


def is_running(url=OMNIROUTE_DEFAULT_URL):
    try:
        req = urllib.request.Request(f"{url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def install():
    print("  Instalando OmniRoute...")
    if not shutil.which("git"):
        print("  [ERRO] git nao encontrado. Instale o git e tente novamente.")
        return False
    if OMNIROUTE_DIR.exists():
        print(f"  [INFO] {OMNIROUTE_DIR} ja existe — pulando clone.")
    else:
        result = subprocess.run(
            ["git", "clone", OMNIROUTE_REPO, str(OMNIROUTE_DIR)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  [ERRO] git clone falhou: {result.stderr[:200]}")
            return False
    req_file = OMNIROUTE_DIR / "requirements.txt"
    if req_file.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  [AVISO] pip install com erros: {result.stderr[:200]}")
    print(f"  [OK] OmniRoute instalado em {OMNIROUTE_DIR}")
    print(f"  Para iniciar: cd {OMNIROUTE_DIR} && python3 server.py")
    return True


def check_or_install():
    """Retorna True se OmniRoute esta respondendo (apos instalar se necessario)."""
    if is_running():
        print("  [OK] OmniRoute respondendo em", OMNIROUTE_DEFAULT_URL)
        return True

    print("  [AVISO] OmniRoute nao esta respondendo em", OMNIROUTE_DEFAULT_URL)
    try:
        resp = input("  Instalar OmniRoute agora? (s/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if resp == "s":
        installed = install()
        if installed:
            print("  Inicie o OmniRoute em outro terminal e pressione Enter.")
            try:
                input("  [Enter para continuar]: ")
            except (EOFError, KeyboardInterrupt):
                pass
            return is_running()
    return False


if __name__ == "__main__":
    ok = check_or_install()
    sys.exit(0 if ok else 1)
