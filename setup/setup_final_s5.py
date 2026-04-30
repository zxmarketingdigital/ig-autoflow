#!/usr/bin/env python3
"""
Etapa 10 — Finalizacao + Log de Sessao + ZX Control 2.0
Encerramento oficial da Semana 5.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import session_logger
from lib import (
    CHECKPOINT_PATH_S5,
    DATA_DIR,
    load_config,
    mark_checkpoint,
    now_iso,
    save_config,
)

PENDING_PATH = DATA_DIR / "logs" / "pending_push_s5.json"


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
# LaunchAgent do Mission Control (regenera dashboard de hora em hora)
# ---------------------------------------------------------------------------

DASHBOARD_LABEL = "com.zxlab.ig-dashboard"


def _install_dashboard_launchagent():
    """Instala LaunchAgent que regenera o dashboard a cada 1 hora."""
    if sys.platform != "darwin":
        print("  [skip] LaunchAgent so e suportado em macOS — agendamento manual nao instalado.")
        return False

    from lib import INSTAGRAM_DIR, MISSION_CONTROL_DIR

    # Garante que o gerador esta no INSTAGRAM_DIR (junto com lib.py, ig_schemas.py etc)
    src = ROOT_DIR / "scripts" / "ig_dashboard.py"
    dst = INSTAGRAM_DIR / "ig_dashboard.py"
    INSTAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    MISSION_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

    log_path = INSTAGRAM_DIR / "logs" / "ig-dashboard.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    python_path = sys.executable or "/usr/bin/python3"

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{DASHBOARD_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{dst}</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
</dict>
</plist>
"""
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{DASHBOARD_LABEL}.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(plist, encoding="utf-8")

    # Recarrega
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    res = subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  Aviso launchctl load: {res.stderr.strip() or res.stdout.strip()}")
        return False
    print(f"  LaunchAgent instalado: {DASHBOARD_LABEL}")
    return True


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

    session_data = session_logger.collect(CHECKPOINT_PATH_S5)

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
        feedback = session_logger.ask_feedback()
    except Exception as e:
        print(f"  (Feedback ignorado: {e})")

    # [3/6] Salvar log
    _progress(6)
    print("  [3/6] Salvar log (JSON + MD)")
    _sep()

    json_path, md_path = session_logger.write(session_data, feedback)
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

    # [6/6] Mission Control + Conclusao
    _progress(10)
    print("  [6/6] Gerar Mission Control Instagram + Conclusao")
    _sep()

    try:
        _install_dashboard_launchagent()
        from ig_dashboard import render as _render_dashboard
        from lib import open_in_browser as _open
        dash_path = _render_dashboard()
        print(f"  Mission Control gerado: {dash_path}")
        print("  Atualizacao automatica: a cada 1 hora (com.zxlab.ig-dashboard)")
        _open(dash_path)
        print("  Aberto no navegador.")
    except Exception as e:
        print(f"  Aviso: nao foi possivel gerar Mission Control automaticamente ({e})")
        print("  Voce pode rodar manualmente: python3 scripts/ig_dashboard.py --open")
    print()

    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║                                                      ║")
    print("  ║   PARABENS! Automacao Instagram 100% configurada!    ║")
    print("  ║                                                      ║")
    print("  ║   O que voce tem agora:                              ║")
    print("  ║   - Comment Responder detectando keywords 24/7       ║")
    print("  ║   - DM Agent respondendo com Anthropic Claude        ║")
    print("  ║   - Escalacao automatica para WhatsApp (opcional)    ║")
    print("  ║   - Mission Control 5.0 com widgets Instagram        ║")
    print("  ║   - Token refresh automatico                         ║")
    print("  ║                                                      ║")
    print("  ║   Proximo nivel: ZX Control 2.0 — Turma 2            ║")
    print("  ║   Primeira semana de maio/2026                       ║")
    print("  ║                                                      ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    # U#5 — Resumo das automacoes instaladas com comandos prontos
    import os
    from lib import INSTAGRAM_DIR as _IG_DIR
    uid = os.getuid() if hasattr(os, "getuid") else "$(id -u)"
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║  Automacoes instaladas                               ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  com.zxlab.ig-auto  (Comment Responder — a cada 30min)")
    print(f"  Testar agora:  launchctl kickstart -k gui/{uid}/com.zxlab.ig-auto")
    print(f"  Ver log:       tail -f {_IG_DIR}/logs/ig-auto.log")
    print()
    print("  com.zxlab.ig-dm    (DM Agent Anthropic — a cada 5min)")
    print(f"  Testar agora:  launchctl kickstart -k gui/{uid}/com.zxlab.ig-dm")
    print(f"  Ver log:       tail -f {_IG_DIR}/logs/ig-dm.log")
    print()
    print("  com.zxlab.ig-token (Token Refresh — 03h diario)")
    print(f"  Testar agora:  launchctl kickstart -k gui/{uid}/com.zxlab.ig-token")
    print(f"  Ver log:       tail -f {_IG_DIR}/logs/ig-token.log")
    print()
    print("  com.zxlab.ig-dashboard (Mission Control IG — a cada 1h)")
    print(f"  Atualizar ja:  launchctl kickstart -k gui/{uid}/com.zxlab.ig-dashboard")
    from lib import MISSION_CONTROL_DIR as _MC_DIR
    print(f"  Abrir:         open {_MC_DIR}/instagram-dashboard.html")
    print()
    print(f"  Status geral:  python3 {_IG_DIR}/ig_auto_responder.py --status")
    print(f"  Auditoria:     python3 setup/setup_audit_s5.py --with-runtime")
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
