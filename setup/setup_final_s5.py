#!/usr/bin/env python3
"""
Etapa 10 — Finalizacao + Log de Sessao + ZX Control 2.0
Encerramento oficial da Semana 5.
"""

import json
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    CHECKPOINT_PATH_S5,
    DATA_DIR,
    PLATFORM,
    SESSION_LOGS_DIR,
    load_config,
    mark_checkpoint,
    now_iso,
    save_config,
)

PENDING_PATH = DATA_DIR / "logs" / "pending_push_s5.json"


# ---------------------------------------------------------------------------
# session_logger (inline, adaptado para S5)
# ---------------------------------------------------------------------------

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
                data = raw.get("steps", raw)
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
        except Exception:
            feedback[0] = ""
        finally:
            done.set()

    t = threading.Thread(target=_input_thread, daemon=True)
    t.start()
    got_input = done.wait(timeout=60)
    if not got_input:
        print("\n  (Timeout — continuando sem feedback)")
    return feedback[0]


def write_session(session_data, feedback):
    SESSION_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    base_name = f"session-s5-{now_str}"

    payload = dict(session_data)
    payload["feedback"] = feedback

    json_path = SESSION_LOGS_DIR / f"{base_name}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = SESSION_LOGS_DIR / f"{base_name}.md"
    dur = session_data.get("duration_seconds", 0)
    dur_min, dur_sec = dur // 60, dur % 60
    checkpoints = session_data.get("checkpoints", {})
    done_count = sum(1 for v in checkpoints.values() if isinstance(v, dict) and v.get("status") == "done")
    total_count = max(len(checkpoints), 10)

    started_at = session_data.get("started_at", "")
    try:
        dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        data_legivel = dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        data_legivel = started_at

    table_rows = []
    for step, info in checkpoints.items():
        status = info.get("status", "pending") if isinstance(info, dict) else str(info)
        detail = info.get("detail", "") if isinstance(info, dict) else ""
        icon = "OK" if status == "done" else "PENDENTE"
        table_rows.append(f"| {step} | {icon} | {detail} |")

    table_body = "\n".join(table_rows) if table_rows else "| — | — | — |"

    md_content = f"""# Log Sessao S5 — {data_legivel}

**Plataforma:** {session_data.get('platform', 'unknown')}
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


# ---------------------------------------------------------------------------
# supabase_log_push (inline, adaptado para S5)
# ---------------------------------------------------------------------------

def _load_pending():
    if PENDING_PATH.exists():
        try:
            data = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _save_pending(pending_list):
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps(pending_list, ensure_ascii=False, indent=2), encoding="utf-8")


def _push(session_json_path, config):
    supabase_url = config.get("supabase_url", "").rstrip("/")
    anon_key = config.get("supabase_anon_key", "")
    if not supabase_url or not anon_key:
        raise ValueError("Supabase nao configurado")
    session_json_path = Path(session_json_path)
    payload_bytes = session_json_path.read_bytes()
    url = f"{supabase_url}/functions/v1/session-log-s5"
    req = urllib.request.Request(url, data=payload_bytes, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {anon_key}",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        try:
            return json.loads(body)
        except Exception:
            return {"status": "ok", "raw": body}


def supabase_log_push(session_json_path, config, max_retries=3):
    supabase_url = config.get("supabase_url", "")
    anon_key = config.get("supabase_anon_key", "")

    if not supabase_url or not anon_key:
        pending = _load_pending()
        if str(session_json_path) not in pending:
            pending.append(str(session_json_path))
        _save_pending(pending)
        return False, "Supabase nao configurado — log salvo localmente"

    last_error = None
    for attempt in range(max_retries):
        try:
            _push(session_json_path, config)
            return True, None
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))

    pending = _load_pending()
    if str(session_json_path) not in pending:
        pending.append(str(session_json_path))
    _save_pending(pending)
    return False, f"Falha apos {max_retries} tentativas: {last_error}"


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

def _progress(step, total=10):
    filled = "█" * step
    empty = "░" * (total - step)
    print(f"\n  [{filled}{empty}] Etapa 10 de 10")


def _sep():
    print("  " + "─" * 52)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ║   Etapa 10 — Finalizacao + Log + ZX Control 2.0      ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as exc:
        print(f"  Aviso: config.json indisponivel ({exc}). Continuando sem Supabase.")
        config = {}

    # [1/6] Coletar dados da sessao
    _progress(2)
    print("  [1/6] Coletar dados da sessao")
    _sep()

    session_data = collect(CHECKPOINT_PATH_S5)

    dur_min = session_data["duration_seconds"] // 60
    dur_sec = session_data["duration_seconds"] % 60
    done_count = sum(
        1 for v in session_data["checkpoints"].values()
        if isinstance(v, dict) and v.get("status") == "done"
    )
    total_steps = max(len(session_data["checkpoints"]), 10)

    print(f"  Plataforma  : {session_data['platform']}")
    print(f"  Iniciado em : {session_data['started_at']}")
    print(f"  Duracao     : {dur_min}min {dur_sec}s")
    print(f"  Concluidos  : {done_count}/{total_steps} etapas")

    if session_data["errors"]:
        print(f"  Pendencias  : {len(session_data['errors'])} etapa(s) incompleta(s)")
        for err in session_data["errors"]:
            print(f"    - {err['step']}: {err['detail']}")

    # [2/6] Feedback
    _progress(4)
    print("  [2/6] Coletar feedback do aluno")
    _sep()
    print()

    feedback = ""
    try:
        feedback = ask_feedback()
    except Exception as e:
        print(f"  (Feedback ignorado: {e})")

    # [3/6] Salvar log
    _progress(6)
    print("  [3/6] Salvar log (JSON + MD)")
    _sep()

    json_path, md_path = write_session(session_data, feedback)
    print(f"  JSON: {json_path}")
    print(f"  MD  : {md_path}")

    # [4/6] Enviar para Supabase
    _progress(7)
    print("  [4/6] Enviar log para Supabase")
    _sep()

    success, error = supabase_log_push(json_path, config)
    if success:
        print("  Seu log foi enviado!")
    else:
        print("  Log salvo localmente. Sera enviado na proxima sessao.")
        if error:
            print(f"  Detalhe: {error}")

    # [5/6] Atualizar config.json
    _progress(8)
    print("  [5/6] Atualizar config.json")
    _sep()

    config["phase_completed"] = 5
    config["week5"] = {
        "completed": True,
        "completed_at": now_iso(),
    }
    try:
        save_config(config)
        print("  config.json atualizado: phase_completed=5, week5.completed=True")
    except Exception as e:
        print(f"  Aviso: nao foi possivel salvar config.json: {e}")

    # [6/6] Conclusao
    _progress(10)
    print("  [6/6] Conclusao")
    _sep()
    print()

    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║                                                      ║")
    print("  ║   PARABENS! Automacao Instagram 100% configurada!    ║")
    print("  ║                                                      ║")
    print("  ║   O que voce tem agora:                              ║")
    print("  ║   - Comment Responder detectando keywords 24/7       ║")
    print("  ║   - DM Agent respondendo com base de conhecimento    ║")
    print("  ║   - Escalacao automatica para WhatsApp               ║")
    print("  ║   - Mission Control 5.0 com widgets Instagram        ║")
    print("  ║   - Token refresh automatico                         ║")
    print("  ║                                                      ║")
    print("  ║   Proximo nivel: ZX Control 2.0 — Turma 2            ║")
    print("  ║   Primeira semana de maio/2026                       ║")
    print("  ║                                                      ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    # Pitch para visitantes do repositorio publico
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║  Voce esta vendo isso no repositorio publico?        ║")
    print("  ║  Conheca o ZX Control — Mentoria de 30 dias          ║")
    print("  ║  https://zxlab.com.br/mission-control                ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    mark_checkpoint("step_10_final_s5", "done", "Semana 5 concluida")

    print("  Semana 5 concluida! Nos vemos na Turma 2 do ZX Control!")
    print()


if __name__ == "__main__":
    main()
