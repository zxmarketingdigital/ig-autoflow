#!/usr/bin/env python3
"""
ig_dm_agent.py — Responde DMs recebidas no Instagram usando Anthropic SDK + base de conhecimento.
Roda via LaunchAgent/cron a cada N minutos.
"""

import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
from lib import (
    IG_ENV_PATH, IG_DM_SESSIONS_PATH, IG_KB_PATH, INSTAGRAM_DIR,
    load_env_var, now_iso,
)
from ig_schemas import validate_products, products_to_kb_text

BASE_URL = "https://graph.instagram.com/v22.0"
LOG_FILE = INSTAGRAM_DIR / "logs" / "ig-dm.log"
ESCALATION_KEYWORDS = ["humano", "atendente", "falar com alguem", "quero falar", "pessoa real"]

CONVS_SCAN_LIMIT = int(os.environ.get("IG_CONVS_SCAN_LIMIT", "50"))


def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = f"[{now_iso()}] {msg}"
    print(entry, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_db():
    IG_DM_SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(IG_DM_SESSIONS_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            conversation_id TEXT PRIMARY KEY,
            last_message_id TEXT,
            last_seen_at TEXT,
            responded_at TEXT
        )
    """)
    conn.commit()
    return conn


def api_get(path, token, params=None):
    p = {"access_token": token}
    if params:
        p.update(params)
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(p)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def _api_raw(url):
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def api_post(path, token, body):
    url = f"{BASE_URL}{path}?access_token={urllib.parse.quote(token)}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_all_conversations(token, user_id, max_total=CONVS_SCAN_LIMIT):
    collected = []
    next_url = None
    params = {"platform": "instagram", "fields": "id,updated_time", "limit": "50"}
    while len(collected) < max_total:
        if next_url:
            resp = _api_raw(next_url)
        else:
            resp = api_get(f"/{user_id}/conversations", token, params)
        collected.extend(resp.get("data", []))
        next_url = resp.get("paging", {}).get("next")
        if not next_url:
            break
    return collected[:max_total]


def call_anthropic(prompt, kb_context, anthropic_key=None):
    import anthropic
    client = anthropic.Anthropic(api_key=anthropic_key) if anthropic_key else anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=f"Voce e um assistente de vendas amigavel. Responda de forma concisa e direta. Base de conhecimento:\n\n{kb_context}",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def send_whatsapp_escalation(evolution_base, instance, whatsapp_number, sender_username):
    url = f"{evolution_base}/message/sendText/{instance}"
    payload = {
        "number": whatsapp_number,
        "text": f"Lead no Instagram precisando de atendimento humano!\nUsuario: @{sender_username}\nResponda pelo Instagram DM.",
    }
    data = json.dumps(payload).encode()
    # Evolution exige header apikey — sem ele o POST retorna 401
    headers = {"Content-Type": "application/json"}
    apikey = load_env_var(IG_ENV_PATH, "EVOLUTION_APIKEY") or ""
    if apikey:
        headers["apikey"] = apikey
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


def load_kb():
    if not IG_KB_PATH.exists():
        return "Sem base de conhecimento configurada."
    try:
        kb_data = json.loads(IG_KB_PATH.read_text(encoding="utf-8"))
        products = validate_products(kb_data)
        return products_to_kb_text(products)
    except (json.JSONDecodeError, ValueError):
        # fallback: arquivo legado em formato Python
        return IG_KB_PATH.read_text(encoding="utf-8")


def main():
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    user_id = load_env_var(IG_ENV_PATH, "IG_USER_ID")
    anthropic_key = load_env_var(IG_ENV_PATH, "ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    evolution_base = load_env_var(IG_ENV_PATH, "EVOLUTION_BASE") or ""
    evolution_instance = load_env_var(IG_ENV_PATH, "EVOLUTION_INSTANCE") or ""
    whatsapp_number = load_env_var(IG_ENV_PATH, "USER_WHATSAPP_NUMBER") or ""

    if not token or not user_id:
        log("[ERRO] Credenciais ausentes em instagram.env")
        sys.exit(1)

    if not anthropic_key:
        log("[ERRO] ANTHROPIC_API_KEY nao encontrada. Configure no instagram.env ou no ambiente.")
        sys.exit(1)

    kb_context = load_kb()
    db = get_db()
    cursor = db.cursor()

    # Primeira execucao: semear sessoes SEM responder — evita tratar o backlog
    # de conversas antigas como mensagens novas e responder todas de uma vez.
    cursor.execute("SELECT COUNT(*) FROM sessions")
    seeding = cursor.fetchone()[0] == 0
    if seeding:
        log("[SEED] Primeira execucao: registrando conversas existentes sem responder.")

    conversations = fetch_all_conversations(token, user_id, max_total=CONVS_SCAN_LIMIT)
    log(f"Conversas encontradas: {len(conversations)}")

    for conv in conversations:
        conv_id = conv["id"]

        cursor.execute("SELECT last_message_id, responded_at FROM sessions WHERE conversation_id=?", (conv_id,))
        row = cursor.fetchone()
        last_msg_id = row[0] if row else None

        msgs_resp = api_get(f"/{conv_id}", token, {"fields": "messages{id,from,message,created_time}"})
        messages = msgs_resp.get("messages", {}).get("data", [])

        new_msgs = []
        for msg in messages:
            if msg["id"] == last_msg_id:
                break
            from_id = msg.get("from", {}).get("id", "")
            if from_id != user_id:
                new_msgs.append(msg)

        if not new_msgs:
            continue

        latest = new_msgs[0]
        msg_text = latest.get("message", "")
        sender = latest.get("from", {}).get("username", latest.get("from", {}).get("id", "?"))

        # Seeding: registra o ponteiro e pula (nao responde backlog).
        # Mensagem sem texto (midia/emoji/story reply): registra e pula.
        if seeding or not msg_text.strip():
            if not seeding:
                log(f"[SKIP] DM sem texto de @{sender} — registrada sem resposta.")
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (conversation_id, last_message_id, last_seen_at, responded_at)
                VALUES (?, ?, ?, ?)
            """, (conv_id, latest["id"], now_iso(), None))
            db.commit()
            continue

        needs_escalation = any(kw in msg_text.lower() for kw in ESCALATION_KEYWORDS)

        if needs_escalation:
            log(f"Escalando conversa {conv_id[:20]}... para WhatsApp @{sender}")
            escalation_msg = "Entendido! Vou chamar um especialista humano para continuar o atendimento. Aguarde um momento."
            try:
                api_post(f"/{user_id}/messages", token, {
                    "recipient": {"id": latest.get("from", {}).get("id", "")},
                    "message": {"text": escalation_msg},
                })
                if evolution_base and evolution_instance and whatsapp_number:
                    send_whatsapp_escalation(evolution_base, evolution_instance, whatsapp_number, sender)
                log(f"  [OK] Escalacao enviada para @{sender}")
            except Exception as e:
                log(f"  [ERRO] Escalacao falhou: {e}")
        else:
            log(f"Respondendo DM de @{sender}: '{msg_text[:40]}'")
            try:
                response_text = call_anthropic(msg_text, kb_context, anthropic_key)
                api_post(f"/{user_id}/messages", token, {
                    "recipient": {"id": latest.get("from", {}).get("id", "")},
                    "message": {"text": response_text},
                })
                log(f"  [OK] dm_respondida para @{sender}")
            except Exception as e:
                log(f"  [ERRO] Resposta falhou: {e}")

        cursor.execute("""
            INSERT OR REPLACE INTO sessions (conversation_id, last_message_id, last_seen_at, responded_at)
            VALUES (?, ?, ?, ?)
        """, (conv_id, latest["id"], now_iso(), now_iso()))
        db.commit()

    db.close()
    log("Ciclo DM concluido.")


if __name__ == "__main__":
    status_mode = "--status" in sys.argv
    if status_mode:
        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        print(f"Conversas rastreadas: {count}")
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
            print(f"Ultimo log: {lines[-1] if lines else '(vazio)'}")
        db.close()
    else:
        main()
