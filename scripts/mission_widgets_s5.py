#!/usr/bin/env python3
"""Widgets do Mission Control 5.0 para o Instagram auto-responder."""

import json
from datetime import datetime
from pathlib import Path
import sys

_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
from lib import IG_ENV_PATH, INSTAGRAM_DIR, load_env_var, now_iso


def _last_log_line(log_file):
    p = Path(log_file)
    if not p.exists():
        return "Sem logs ainda"
    lines = p.read_text(encoding="utf-8").splitlines()
    return lines[-1] if lines else "Sem logs ainda"


def _count_log_pattern(log_file, pattern, hours=24):
    p = Path(log_file)
    if not p.exists():
        return 0
    cutoff = datetime.now().timestamp() - hours * 3600
    count = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if pattern in line:
            count += 1
    return count


def _token_days_left():
    generated = load_env_var(IG_ENV_PATH, "IG_TOKEN_GENERATED_AT") or ""
    if not generated:
        return None
    try:
        gen_dt = datetime.strptime(generated, "%Y-%m-%d")
        elapsed = (datetime.now() - gen_dt).days
        return max(0, 60 - elapsed)
    except Exception:
        return None


def get_widgets():
    auto_log = INSTAGRAM_DIR / "logs" / "ig-auto.log"
    dm_log = INSTAGRAM_DIR / "logs" / "ig-dm.log"

    comments_processed = _count_log_pattern(auto_log, "comment_id processado")
    auto_errors = _count_log_pattern(auto_log, "[ERRO]")
    auto_last = _last_log_line(auto_log)

    dms_responded = _count_log_pattern(dm_log, "[OK] Resposta enviada")
    escalations = _count_log_pattern(dm_log, "Escalando conversa")
    dm_errors = _count_log_pattern(dm_log, "[ERRO]")
    dm_last = _last_log_line(dm_log)

    days_left = _token_days_left()
    token_color = "red" if days_left is not None and days_left < 5 else "green"

    return [
        {
            "id": "ig-auto-responder",
            "title": "IG Auto-Responder",
            "metrics": [
                {"label": "Comentários 24h", "value": comments_processed},
                {"label": "Erros 24h", "value": auto_errors, "color": "red" if auto_errors else "green"},
                {"label": "Último run", "value": auto_last[:60]},
            ],
        },
        {
            "id": "ig-dm-agent",
            "title": "IG DM Agent",
            "metrics": [
                {"label": "DMs respondidas 24h", "value": dms_responded},
                {"label": "Escalações 24h", "value": escalations},
                {"label": "Erros 24h", "value": dm_errors, "color": "red" if dm_errors else "green"},
                {"label": "Último run", "value": dm_last[:60]},
            ],
        },
        {
            "id": "ig-token-age",
            "title": "IG Token",
            "metrics": [
                {
                    "label": "Dias até expirar",
                    "value": days_left if days_left is not None else "?",
                    "color": token_color,
                },
            ],
        },
    ]


if __name__ == "__main__":
    for w in get_widgets():
        print(f"\n=== {w['title']} ===")
        for m in w["metrics"]:
            print(f"  {m['label']}: {m['value']}")
