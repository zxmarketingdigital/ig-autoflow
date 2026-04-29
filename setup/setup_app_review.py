#!/usr/bin/env python3
"""
Etapa 3 — App Review
Verifica se o app ja esta em modo Live; se nao, gera Privacy Policy,
orienta submissao para App Review e aguarda aprovacao.
"""

import json
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    IG_ENV_PATH,
    load_env_var,
    mark_checkpoint,
    open_in_browser,
)

IG_API_BASE = "https://graph.instagram.com/v22.0"

CASE_USE_COMMENTS = (
    "Esta automacao detecta palavras-chave em comentarios do Instagram Business "
    "do proprio usuario e envia respostas automaticas (reply publico + DM privada). "
    "Toda a automacao roda localmente no computador do dono da conta."
)

CASE_USE_MESSAGES = (
    "Esta automacao gerencia DMs recebidas no Instagram Business do proprio usuario, "
    "respondendo com base em uma base de conhecimento configurada pelo dono da conta. "
    "Escalacao para WhatsApp pessoal disponivel quando solicitado."
)


def ask(prompt, secret=False, default=None):
    import getpass
    display = f"  {prompt}"
    if default:
        display += f" [{default}]"
    display += ": "
    try:
        if secret:
            value = getpass.getpass(display).strip()
        else:
            value = input(display).strip()
        return value if value else (default or "")
    except (KeyboardInterrupt, EOFError):
        print()
        print("  Setup cancelado.")
        sys.exit(0)


def _ig_get(endpoint, token):
    url = f"{IG_API_BASE}{endpoint}?access_token={token}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            return None, json.loads(body)
        except Exception:
            return None, {"error": {"message": f"HTTP {e.code}"}}
    except urllib.error.URLError as e:
        return None, {"error": {"message": str(e.reason)}}


def load_token():
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    if not token:
        print("  [ERRO] IG_ACCESS_TOKEN nao encontrado em instagram.env.")
        print("  Execute primeiro: python3 setup/setup_meta_app.py")
        sys.exit(1)
    return token


def load_user_id():
    uid = load_env_var(IG_ENV_PATH, "IG_USER_ID")
    if not uid:
        print("  [ERRO] IG_USER_ID nao encontrado em instagram.env.")
        sys.exit(1)
    return uid


def load_app_id():
    return load_env_var(IG_ENV_PATH, "IG_APP_ID_INSTAGRAM") or "SEU_APP_ID"


def get_first_media_id(token):
    data, err = _ig_get("/me/media", token)
    if err or not data:
        return None
    posts = data.get("data", [])
    return posts[0]["id"] if posts else None


def check_live_mode(media_id, token):
    """Retorna True se comentarios reais sao retornados (app esta em Live)."""
    data, err = _ig_get(f"/{media_id}/comments", token)
    if err:
        return False
    comments = data.get("data", [])
    return len(comments) > 0


def run_live_validation(token, user_id, media_id):
    all_ok = True

    print("  Teste L1: Lendo comentarios de post real...")
    data, err = _ig_get(f"/{media_id}/comments", token)
    if err:
        msg = err.get("error", {}).get("message", str(err))
        print(f"  [FALHA] GET /{media_id}/comments: {msg}")
        print("  App ainda em Development mode. Aguarde a aprovacao e tente novamente.")
        all_ok = False
    else:
        comments = data.get("data", [])
        print(f"  [OK] {len(comments)} comentario(s) lido(s).")

    print("  Teste L2: Lendo conversations...")
    data2, err2 = _ig_get(f"/{user_id}/conversations", token)
    if err2:
        code = err2.get("error", {}).get("code", 0)
        msg = err2.get("error", {}).get("message", str(err2))
        if code in (10, 200, 190):
            print(f"  [FALHA] Permissao negada (code={code}): {msg}")
            all_ok = False
        else:
            print(f"  [OK] Conversations respondeu (pode estar vazio).")
    else:
        convs = data2.get("data", [])
        print(f"  [OK] {len(convs)} conversa(s) encontrada(s).")

    return all_ok


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [███░░░░░░░] Etapa 3 de 10")
    print()
    print("  Etapa 3 — App Review (modo Live)")
    print()

    token = load_token()
    user_id = load_user_id()
    app_id = load_app_id()

    media_id = get_first_media_id(token)
    if not media_id:
        print("  [ERRO] Nenhum post encontrado. Publique ao menos 1 post no Instagram.")
        sys.exit(1)

    # Verificar se ja esta em modo Live
    print("  Verificando se app ja esta em modo Live...")
    if check_live_mode(media_id, token):
        print("  [OK] App ja esta em modo Live! Pulando para validacao final.")
        print()
    else:
        print("  App ainda em Development mode.")
        print()

        # --- Gerar Privacy Policy ---
        print("  ─── GERAR PRIVACY POLICY ───────────────────────────")
        print()
        nome = ask("Seu nome completo")
        email = ask("Seu e-mail de contato")
        app_nome = ask("Nome do App", default="Automacao Instagram")

        privacy_url = (
            "https://ig-privacy-rcastro.pages.dev"
            f"?name={urllib.parse.quote(nome)}"
            f"&email={urllib.parse.quote(email)}"
            f"&app={urllib.parse.quote(app_nome)}"
        )

        print()
        print(f"  URL da Privacy Policy gerada:")
        print(f"  {privacy_url}")
        print()
        open_in_browser(privacy_url)
        print("  [OK] Abrindo no browser...")
        print()
        print("  IMPORTANTE: Copie a URL acima — voce vai precisar dela no Meta.")
        ask("Pressione Enter para continuar")
        print()

        # --- Adicionar Privacy Policy no Meta ---
        print("  ─── ADICIONAR PRIVACY POLICY NO META APP ───────────")
        print()
        print(f"  1. Acesse: https://developers.facebook.com/apps/{app_id}")
        print("  2. Clique em 'Configuracoes' → 'Basico'")
        print(f"  3. No campo 'URL da Politica de Privacidade' cole:")
        print(f"     {privacy_url}")
        print("  4. Clique 'Salvar alteracoes'")
        print()
        ask("Pressione Enter quando salvar a Privacy Policy")
        print()

        # --- Submeter para App Review ---
        print("  ─── SUBMETER PARA APP REVIEW ────────────────────────")
        print()
        print(f"  1. No painel do app: https://developers.facebook.com/apps/{app_id}")
        print("  2. Clique em 'Analise do App' no menu lateral")
        print("  3. Clique em 'Permissoes e Recursos'")
        print()
        print("  4. Encontre 'instagram_business_manage_comments'")
        print("     → Clique 'Solicitar Acesso Avancado'")
        print("     → Cole a descricao do caso de uso:")
        print()
        print(f"     \"{CASE_USE_COMMENTS}\"")
        print()
        print("  5. Encontre 'instagram_business_manage_messages'")
        print("     → Clique 'Solicitar Acesso Avancado'")
        print("     → Cole a descricao do caso de uso:")
        print()
        print(f"     \"{CASE_USE_MESSAGES}\"")
        print()
        print("  6. Clique 'Enviar para Revisao'")
        print()
        print("  Prazo esperado: 2-5 dias uteis.")
        print()
        ask("Pressione Enter quando o App Review for aprovado e o app estiver em modo Live")
        print()

    # --- Validacao pos-Live ---
    print("  Executando validacao pos-Live...")
    print()
    ok = run_live_validation(token, user_id, media_id)

    if not ok:
        print()
        print("  Validacao falhou. Aguarde a aprovacao completa e execute novamente.")
        sys.exit(1)

    print()
    mark_checkpoint("step_3_app_review", "done", "live_mode=true")

    print("  [OK] Etapa 3 concluida!")
    print()
    print("  Proximo: python3 setup/setup_comment_responder.py")
    print()


if __name__ == "__main__":
    main()
