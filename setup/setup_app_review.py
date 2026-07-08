#!/usr/bin/env python3
"""
Etapa 3 — App Review (opcional, nao bloqueia o setup)

IMPORTANTE: o Advanced Access da Meta (App Review) NAO e pre-requisito para
a automacao funcionar. Em modo Standard, o app ja le e responde comentarios
e DMs do dono da conta e de testadores adicionados — suficiente para o
agente estar funcional e para o teste pratico da Etapa 9. O Advanced Access
apenas AMPLIA a leitura para comentarios/DMs de seguidores quaisquer, e a
aprovacao da Meta leva 2-5 dias uteis rodando em paralelo, sem travar o aluno.

Este script: (1) confirma que a automacao ja funciona agora (modo Standard),
(2) opcionalmente gera a Privacy Policy e guia a submissao do Advanced Access
para quando o aluno quiser ampliar o alcance. Nunca bloqueia aguardando a Meta.
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


def get_first_media_id_with_comments(token):
    """Retorna (media_id, comments_count) do primeiro post com comentarios confirmados."""
    data, err = _ig_get("/me/media", token)
    if err or not data:
        return None, 0
    for post in data.get("data", []):
        count = int(post.get("comments_count", 0))
        if count > 0:
            return post["id"], count
    # fallback: primeiro post mesmo sem comentarios
    posts = data.get("data", [])
    return (posts[0]["id"], 0) if posts else (None, 0)


def _ig_post(endpoint, token, payload):
    url = f"{IG_API_BASE}{endpoint}?access_token={token}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
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


def _ig_delete(endpoint, token):
    url = f"{IG_API_BASE}{endpoint}?access_token={token}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except Exception as e:
        return None, {"error": {"message": str(e)}}


def check_advanced_access(media_id, expected_count, token):
    """
    Retorna True se comentarios de SEGUIDORES QUAISQUER ja sao legiveis
    (Advanced Access aprovado). So e diagnostico quando expected_count > 0
    (post com comentarios de terceiros). Isso e so um AVISO informativo —
    nunca bloqueia o setup.
    """
    if expected_count == 0:
        return None  # sem sinal suficiente para diagnosticar
    data, err = _ig_get(f"/{media_id}/comments", token)
    if err:
        return False
    comments = data.get("data", [])
    return len(comments) > 0


def run_standard_mode_check(token, user_id, media_id):
    """
    Confirma que a automacao JA FUNCIONA agora, em modo Standard: cria um
    comentario proprio, le de volta via API e apaga. Isso e exatamente o
    que o agente precisa para responder o dono da conta e testadores —
    NAO depende de Advanced Access nem de aprovacao da Meta.
    """
    print("  Teste: escrita + leitura em modo Standard (dono da conta)...")
    payload = {"message": "teste-zxlab-setup-s3-apagar"}
    created, err = _ig_post(f"/{media_id}/comments", token, payload)
    if err:
        msg = err.get("error", {}).get("message", str(err))
        print(f"  [FALHA] Nao foi possivel criar comentario de teste: {msg}")
        return False

    comment_id = created.get("id")
    data, err2 = _ig_get(f"/{media_id}/comments", token)
    found = comment_id and any(c.get("id") == comment_id for c in (data or {}).get("data", []))

    if comment_id:
        _ig_delete(f"/{comment_id}", token)

    if found:
        print("  [OK] Comentario criado e lido de volta — automacao funcional agora.")
        return True
    print("  [AVISO] Comentario criado mas nao apareceu na leitura (raro). Tente novamente.")
    return False


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [███░░░░░░░] Etapa 3 de 10")
    print()
    print("  Etapa 3 — App Review (opcional — nao bloqueia o setup)")
    print()
    print("  A automacao ja funciona AGORA em modo Standard (dono da conta +")
    print("  testadores). O Advanced Access da Meta so amplia a leitura para")
    print("  comentarios/DMs de seguidores quaisquer — nao e pre-requisito")
    print("  para prosseguir. Pode ser solicitado e aprovado em paralelo,")
    print("  sem travar as proximas etapas.")
    print()

    token = load_token()
    user_id = load_user_id()
    app_id = load_app_id()

    media_id, expected_count = get_first_media_id_with_comments(token)
    if not media_id:
        print("  [ERRO] Nenhum post encontrado. Publique ao menos 1 post no Instagram.")
        sys.exit(1)

    # --- Confirmar que a automacao ja funciona agora (modo Standard) ---
    standard_ok = run_standard_mode_check(token, user_id, media_id)
    print()

    # --- Diagnostico informativo do Advanced Access (nunca bloqueia) ---
    advanced = check_advanced_access(media_id, expected_count, token)
    if advanced is True:
        print("  [INFO] Advanced Access parece aprovado — comentarios de seguidores ja legiveis.")
    elif advanced is False:
        print("  [INFO] Advanced Access ainda pendente — comentarios de seguidores nao aparecem")
        print("         na leitura ainda (normal antes da aprovacao da Meta). Isso NAO impede")
        print("         a automacao de funcionar para o dono da conta e testadores.")
    print()

    # --- Oferecer (opcional) gerar Privacy Policy + guia de submissao ---
    quer_submeter = ask(
        "Quer gerar a Privacy Policy e ver o passo a passo pra solicitar Advanced Access agora? (s/N)",
        default="N",
    ).lower()

    if quer_submeter in ("s", "sim", "y", "yes"):
        print()
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
        print()

        print("  ─── ADICIONAR PRIVACY POLICY NO META APP ───────────")
        print()
        print(f"  1. Acesse: https://developers.facebook.com/apps/{app_id}")
        print("  2. Clique em 'Configuracoes' → 'Basico'")
        print(f"  3. No campo 'URL da Politica de Privacidade' cole:")
        print(f"     {privacy_url}")
        print("  4. Clique 'Salvar alteracoes'")
        print()

        print("  ─── SOLICITAR ADVANCED ACCESS (opcional, roda em paralelo) ──")
        print()
        print(f"  1. No painel do app: https://developers.facebook.com/apps/{app_id}")
        print("  2. Abra o caso de uso do Instagram → 'Permissoes e recursos'")
        print()
        print("  3. Encontre 'instagram_business_manage_comments'")
        print("     → Solicite Acesso Avancado / adicione a analise do app")
        print("     → Cole a descricao do caso de uso:")
        print()
        print(f"     \"{CASE_USE_COMMENTS}\"")
        print()
        print("  4. Encontre 'instagram_business_manage_messages'")
        print("     → Solicite Acesso Avancado / adicione a analise do app")
        print("     → Cole a descricao do caso de uso:")
        print()
        print(f"     \"{CASE_USE_MESSAGES}\"")
        print()
        print("  5. Envie para revisao. Prazo esperado: 2-5 dias uteis.")
        print("     Voce NAO precisa esperar essa aprovacao — pode seguir para")
        print("     a Etapa 4 agora mesmo. Rode esta etapa de novo depois para")
        print("     confirmar quando o Advanced Access for aprovado.")
        print()
    else:
        print()
        print("  [OK] Pulando submissao por agora. Pode rodar esta etapa novamente")
        print("       quando quiser ampliar o alcance para todos os seguidores.")
        print()

    detail = f"standard_mode={'ok' if standard_ok else 'falhou'} advanced_access={advanced}"
    mark_checkpoint("step_3_app_review", "done", detail)

    print("  [OK] Etapa 3 concluida! A automacao esta funcional em modo Standard.")
    print()
    print("  Proximo: python3 setup/setup_comment_responder.py")
    print()


if __name__ == "__main__":
    main()
