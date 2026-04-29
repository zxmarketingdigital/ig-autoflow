#!/usr/bin/env python3
"""session_logger.py — Coleta e salva log da sessao da Semana 5."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
import sys

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lib import SESSION_LOGS_DIR, PLATFORM, now_iso


def _parse_iso(ts_str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def collect(checkpoint_path):
    checkpoint_path = Path(checkpoint_path)
    checkpoints = {}
    errors = []
    timestamps = []

    if checkpoint_path.exists():
        try:
            raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw.get("checkpoints", raw)
                for step, info in data.items():
                    if isinstance(info, dict):
                        status = info.get("status", "pending")
                        detail = info.get("detail", "")
                        updated_at = info.get("updated_at", "")
                        checkpoints[step] = {"status": status, "detail": detail, "updated_at": updated_at}
                        if status != "done":
                            errors.append({"step": step, "detail": detail or status})
                        ts = _parse_iso(updated_at)
                        if ts:
                            timestamps.append(ts)
        except Exception as e:
            errors.append({"step": "_checkpoint_load", "detail": str(e)})

    finished_dt = datetime.now()
    finished_at = now_iso()
    if timestamps:
        started_dt = min(timestamps)
        started_at = started_dt.isoformat()
        duration_seconds = int((finished_dt - started_dt).total_seconds())
    else:
        started_at = finished_at
        duration_seconds = 0

    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "checkpoints": checkpoints,
        "errors": errors,
        "platform": PLATFORM,
    }


def ask_feedback():
    prompt = "  O que voce gostaria nos proximos Setups? "
    feedback = [""]
    done = threading.Event()

    def _input_thread():
        try:
            feedback[0] = input(prompt)
        except (EOFError, KeyboardInterrupt):
            feedback[0] = ""
        finally:
            done.set()

    t = threading.Thread(target=_input_thread, daemon=True)
    t.start()
    got_input = done.wait(timeout=60)
    if not got_input:
        print("\n  (Timeout — continuando sem feedback)")
    return feedback[0]


def write(session_data, feedback):
    SESSION_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    base_name = f"session-s5-{now_str}"

    payload = dict(session_data)
    payload["feedback"] = feedback

    json_path = SESSION_LOGS_DIR / f"{base_name}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = SESSION_LOGS_DIR / f"{base_name}.md"
    duration_seconds = session_data.get("duration_seconds", 0)
    dur_min = duration_seconds // 60
    dur_sec = duration_seconds % 60
    checkpoints = session_data.get("checkpoints", {})
    done_count = sum(1 for v in checkpoints.values() if isinstance(v, dict) and v.get("status") == "done")
    total_count = len(checkpoints) if checkpoints else 10

    started_at = session_data.get("started_at", "")
    try:
        dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        data_legivel = dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        data_legivel = started_at

    table_rows = []
    for step, info in checkpoints.items():
        if isinstance(info, dict):
            status = info.get("status", "pending")
            detail = info.get("detail", "")
        else:
            status = str(info)
            detail = ""
        icon = "OK" if status == "done" else "PENDENTE"
        table_rows.append(f"| {step} | {icon} | {detail} |")

    table_body = "\n".join(table_rows) if table_rows else "| — | — | — |"

    md_content = f"""# Log Sessao S5 — {data_legivel}

**Plataforma:** {session_data.get("platform", "unknown")}
**Duracao:** {dur_min}min {dur_sec}s
**Etapas concluidas:** {done_count}/{total_count}

## Checkpoints

| Etapa | Status | Detalhe |
|-------|--------|---------|
{table_body}

## Feedback

{feedback if feedback else "(sem feedback)"}
"""
    md_path.write_text(md_content, encoding="utf-8")
    return json_path, md_path
