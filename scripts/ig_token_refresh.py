#!/usr/bin/env python3
"""Renova o long-lived token do Instagram (valido 60 dias)."""

import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
from lib import IG_ENV_PATH, load_env_var, now_iso

# No Windows a tarefa roda via pythonw (sem console) — stdout se perde.
# log() escreve no arquivo alem de imprimir, como os demais agentes.
_LOG_FILE = _SCRIPTS_DIR / "logs" / "ig-token.log"


def log(msg):
    print(msg)
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def refresh_token(token):
    url = (
        "https://graph.instagram.com/refresh_access_token"
        f"?grant_type=ig_refresh_token&access_token={urllib.parse.quote(token)}"
    )
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def update_env(new_token):
    lines = []
    saw_token = False
    saw_generated_at = False
    if IG_ENV_PATH.exists():
        for line in IG_ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("IG_ACCESS_TOKEN="):
                lines.append(f"IG_ACCESS_TOKEN={new_token}")
                saw_token = True
            elif line.startswith("IG_TOKEN_GENERATED_AT="):
                lines.append(f"IG_TOKEN_GENERATED_AT={datetime.now().strftime('%Y-%m-%d')}")
                saw_generated_at = True
            else:
                lines.append(line)
    if not saw_token:
        lines.append(f"IG_ACCESS_TOKEN={new_token}")
    if not saw_generated_at:
        lines.append(f"IG_TOKEN_GENERATED_AT={datetime.now().strftime('%Y-%m-%d')}")
    IG_ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    if not token:
        log("[ERRO] IG_ACCESS_TOKEN nao encontrado em instagram.env")
        sys.exit(1)

    log(f"[{now_iso()}] Renovando token...")
    try:
        data = refresh_token(token)
    except Exception as e:
        log(f"[ERRO] Falha ao renovar token: {e}")
        sys.exit(1)

    new_token = data.get("access_token")
    expires_in = data.get("expires_in", 0)

    if not new_token:
        log(f"[ERRO] Resposta inesperada: {data}")
        sys.exit(1)

    update_env(new_token)
    days = expires_in // 86400
    log(f"[OK] Token renovado. Expira em {days} dias.")


if __name__ == "__main__":
    main()
