#!/usr/bin/env python3
"""
ig_auto_responder.py — Detecta comentarios com palavras-chave e envia reply + Private Reply DM.
Roda via LaunchAgent/cron a cada N minutos.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
from lib import (
    IG_ENV_PATH, IG_STATE_PATH, IG_TRIGGERS_PATH,
    INSTAGRAM_DIR, load_env_var, now_iso,
)
from ig_schemas import validate_triggers

POSTS_SCAN_LIMIT = int(os.environ.get("IG_POSTS_SCAN_LIMIT", "100"))
POSTS_PROCESS_MAX = int(os.environ.get("IG_POSTS_PROCESS_MAX", "50"))

BASE_URL = "https://graph.instagram.com/v22.0"
LOG_FILE = INSTAGRAM_DIR / "logs" / "ig-auto.log"


def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = f"[{now_iso()}] {msg}"
    print(entry, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def api_get(path, token, params=None):
    p = {"access_token": token}
    if params:
        p.update(params)
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(p)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def api_post(path, token, body):
    url = f"{BASE_URL}{path}?access_token={urllib.parse.quote(token)}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def load_state():
    if IG_STATE_PATH.exists():
        try:
            return json.loads(IG_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"processed_comment_ids": []}


def save_state(state):
    IG_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_triggers():
    if not IG_TRIGGERS_PATH.exists():
        return []
    try:
        data = json.loads(IG_TRIGGERS_PATH.read_text(encoding="utf-8"))
        return validate_triggers(data)
    except ValueError as e:
        log(f"[ERRO] ig_triggers.json invalido: {e}")
        return []


def _api_raw(url):
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_all_posts_with_comments(token, max_total=POSTS_SCAN_LIMIT):
    collected = []
    next_url = None
    params = {"fields": "id,comments_count", "limit": "100"}
    while len(collected) < max_total:
        if next_url:
            resp = _api_raw(next_url)
        else:
            resp = api_get("/me/media", token, params)
        collected.extend([p for p in resp.get("data", []) if p.get("comments_count", 0) > 0])
        next_url = resp.get("paging", {}).get("next")
        if not next_url:
            break
    return collected[:max_total]


def match_trigger(text, triggers):
    text_lower = text.lower()
    for t in triggers:
        for kw in t.get("keywords", []):
            if kw.lower() in text_lower:
                return t
    return None


def main(dry_run=False):
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    user_id = load_env_var(IG_ENV_PATH, "IG_USER_ID")
    if not token or not user_id:
        log("[ERRO] IG_ACCESS_TOKEN ou IG_USER_ID ausentes em instagram.env")
        sys.exit(1)

    triggers = load_triggers()
    if not triggers:
        log("[AVISO] Nenhuma palavra-chave configurada em ig_triggers.json")
        return

    state = load_state()
    processed = set(state.get("processed_comment_ids", []))

    posts = fetch_all_posts_with_comments(token, max_total=POSTS_SCAN_LIMIT)
    log(f"Posts com comentarios encontrados: {len(posts)} (limite scan={POSTS_SCAN_LIMIT}, processar={POSTS_PROCESS_MAX})")

    total_processed = 0
    for post in posts[:POSTS_PROCESS_MAX]:
        media_id = post["id"]
        try:
            comments_resp = api_get(f"/{media_id}/comments", token, {"fields": "id,text,username", "limit": "50"})
        except Exception as e:
            log(f"[ERRO] GET comments {media_id}: {e}")
            continue

        for comment in comments_resp.get("data", []):
            cid = comment["id"]
            if cid in processed:
                continue

            text = comment.get("text", "")
            trigger = match_trigger(text, triggers)
            if not trigger:
                continue

            log(f"Keyword detectada: '{text[:40]}' | comment_id={cid}")

            if not dry_run:
                try:
                    api_post(f"/{cid}/replies", token, {"message": trigger["reply_text"]})
                    log(f"  [OK] Reply publico enviado para {cid}")
                except Exception as e:
                    log(f"  [ERRO] Reply falhou: {e}")

                try:
                    api_post(f"/{user_id}/messages", token, {
                        "recipient": {"comment_id": cid},
                        "message": {"text": trigger["dm_text"]},
                    })
                    log(f"  [OK] Private Reply DM enviada para comment_id={cid}")
                except Exception as e:
                    log(f"  [ERRO] Private Reply falhou: {e}")
            else:
                log(f"  [DRY-RUN] Dispararia reply + DM para comment_id={cid}")
                continue

            processed.add(cid)
            total_processed += 1
            time.sleep(0.5)

    state["processed_comment_ids"] = list(processed)[-2000:]
    save_state(state)
    log(f"Ciclo concluido. {total_processed} comentarios processados.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    status_mode = "--status" in sys.argv
    if status_mode:
        state = load_state()
        print(f"Comentarios processados: {len(state.get('processed_comment_ids', []))}")
        print(f"Log: {LOG_FILE}")
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
            print(f"Ultimo log: {lines[-1] if lines else '(vazio)'}")
    else:
        main(dry_run=dry_run)
