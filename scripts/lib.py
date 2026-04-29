#!/usr/bin/env python3
"""
Utilitarios compartilhados da Semana 5 — ZX Control.
Extende lib.py da Semana 4 com paths para automacao Instagram.
"""

import json
import platform
from datetime import datetime
from pathlib import Path


PLATFORM = platform.system()  # "Darwin", "Windows", "Linux"

BASE_DIR = Path.home() / ".operacao-ia"
CONFIG_PATH = BASE_DIR / "config" / "config.json"
CHECKPOINT_PATH = BASE_DIR / "config" / "week4_checkpoint.json"
CHECKPOINT_PATH_S5 = BASE_DIR / "config" / "week5_checkpoint.json"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
SCRIPTS_DIR = BASE_DIR / "scripts"
MISSION_CONTROL_DIR = BASE_DIR / "mission-control"
HEARTBEAT_DIR = LOGS_DIR / "heartbeat"

# Prospecting paths (Semana 3 — mantidos para compatibilidade)
PROSPECTING_DIR = BASE_DIR / "prospecting"
PROSPECTING_LEADS_DIR = PROSPECTING_DIR / "leads"
PROSPECTING_CAMPAIGNS_DIR = PROSPECTING_DIR / "campaigns"
PROSPECTING_DASHBOARDS_DIR = PROSPECTING_DIR / "dashboards"
PROSPECTING_TEMPLATES_DIR = PROSPECTING_DIR / "templates"
PROSPECTING_LOGS_DIR = LOGS_DIR / "prospecting"
PROSPECTING_PROFILE_PATH = BASE_DIR / "config" / "prospecting_profile.json"
PROSPECTS_DB_PATH = DATA_DIR / "prospects.db"
LEADS_JSON_PATH = PROSPECTING_DASHBOARDS_DIR / "leads.json"
DASHBOARD_HTML_PATH = PROSPECTING_DASHBOARDS_DIR / "prospecting-dashboard.html"
RATE_LIMITS_PATH = DATA_DIR / "rate_limits.json"

# Week 4 paths (mantidos para compatibilidade)
WEEK4_LOGS_DIR = LOGS_DIR / "week4"
CODEX_DIR = Path.home() / ".codex"
CODEX_AUTOMATIONS_DIR = CODEX_DIR / "automations"
CODEX_PROJECT_REVIEW_DIR = CODEX_AUTOMATIONS_DIR / "project-review"
GRAPHS_DIR = BASE_DIR / "graphs"
SESSION_LOGS_DIR = DATA_DIR / "logs"

# Week 5 — Automacao Instagram
WEEK5_LOGS_DIR = LOGS_DIR / "week5"
INSTAGRAM_DIR = SCRIPTS_DIR / "instagram"
IG_ENV_PATH = BASE_DIR / "config" / "instagram.env"
IG_STATE_PATH = INSTAGRAM_DIR / "ig_state.json"
IG_TRIGGERS_PATH = INSTAGRAM_DIR / "ig_triggers.json"
IG_DM_SESSIONS_PATH = INSTAGRAM_DIR / "ig_dm_sessions.sqlite"
IG_KB_PATH = INSTAGRAM_DIR / "ig_knowledge_base.py"


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def ensure_structure():
    for path in [
        DATA_DIR, LOGS_DIR, SCRIPTS_DIR, MISSION_CONTROL_DIR, HEARTBEAT_DIR,
        PROSPECTING_DIR, PROSPECTING_LEADS_DIR, PROSPECTING_CAMPAIGNS_DIR,
        PROSPECTING_DASHBOARDS_DIR, PROSPECTING_TEMPLATES_DIR, PROSPECTING_LOGS_DIR,
        BASE_DIR / "config",
        WEEK4_LOGS_DIR,
        CODEX_DIR,
        CODEX_AUTOMATIONS_DIR,
        CODEX_PROJECT_REVIEW_DIR,
        GRAPHS_DIR,
        SESSION_LOGS_DIR,
        # Week 5 new dirs
        WEEK5_LOGS_DIR,
        INSTAGRAM_DIR,
        INSTAGRAM_DIR / "logs",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("config.json nao encontrado em ~/.operacao-ia/config/")
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"config.json invalido (JSON malformado): {exc}") from exc


def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint(path=None):
    target = Path(path) if path else CHECKPOINT_PATH_S5
    if not target.exists():
        return {"steps": {}, "updated_at": None}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {"steps": {}, "updated_at": None}


def save_checkpoint(checkpoint, path=None):
    target = Path(path) if path else CHECKPOINT_PATH_S5
    target.parent.mkdir(parents=True, exist_ok=True)
    checkpoint["updated_at"] = now_iso()
    target.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_checkpoint(step, status, detail=""):
    checkpoint = load_checkpoint()
    checkpoint.setdefault("steps", {})
    checkpoint["steps"][step] = {
        "status": status,
        "detail": detail,
        "updated_at": now_iso(),
    }
    save_checkpoint(checkpoint)


def load_env_var(path, key):
    env_path = Path(path)
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return None


def open_in_browser(url_or_path):
    import subprocess
    path_str = str(url_or_path)
    try:
        if PLATFORM == "Darwin":
            subprocess.run(["open", path_str], check=False)
        elif PLATFORM == "Windows":
            subprocess.run(["start", path_str], shell=True, check=False)
        else:
            subprocess.run(["xdg-open", path_str], check=False)
    except FileNotFoundError:
        pass


def mask_phone(phone):
    if len(phone) >= 10:
        return phone[:4] + "***" + phone[-3:]
    return phone


def latest_heartbeat_snapshot():
    snapshots = {}
    for layer_name in ["watchdog", "heartbeat", "last_resort"]:
        path = HEARTBEAT_DIR / f"{layer_name}.json"
        if not path.exists():
            snapshots[layer_name] = None
            continue
        try:
            snapshots[layer_name] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            snapshots[layer_name] = None
    return snapshots
