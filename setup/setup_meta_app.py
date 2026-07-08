#!/usr/bin/env python3
"""
Etapa 2 — Meta App
Criar app no Meta Developers, gerar token e validar permissoes via smoke tests.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    IG_ENV_PATH,
    mark_checkpoint,
)

IG_API_BASE = "https://graph.instagram.com/v22.0"


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
            return None, {"error": {"message": f"HTTP {e.code}: {body}"}}
    except urllib.error.URLError as e:
        return None, {"error": {"message": str(e.reason)}}


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
            return None, {"error": {"message": f"HTTP {e.code}: {body}"}}
    except urllib.error.URLError as e:
        return None, {"error": {"message": str(e.reason)}}


def _ig_delete(endpoint, token):
    url = f"{IG_API_BASE}{endpoint}?access_token={token}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            return None, json.loads(body)
        except Exception:
            return None, {"error": {"message": f"HTTP {e.code}: {body}"}}
    except urllib.error.URLError as e:
        return None, {"error": {"message": str(e.reason)}}


def save_env(app_id, app_secret, user_id, token):
    from datetime import datetime
    IG_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"IG_APP_ID_INSTAGRAM={app_id}\n"
        f"IG_APP_SECRET={app_secret}\n"
        f"IG_USER_ID={user_id}\n"
        f"IG_ACCESS_TOKEN={token}\n"
        f"IG_TOKEN_GENERATED_AT={datetime.now().strftime('%Y-%m-%d')}\n"
    )
    # Backup do .env anterior antes de sobrescrever (uma única geração de segurança)
    if IG_ENV_PATH.exists():
        try:
            IG_ENV_PATH.with_suffix(IG_ENV_PATH.suffix + ".bak").write_text(
                IG_ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8"
            )
        except Exception:
            pass
    IG_ENV_PATH.write_text(content, encoding="utf-8")
    # Restringe leitura ao dono — tokens de acesso não devem vazar p/ outros usuários do FS
    try:
        os.chmod(IG_ENV_PATH, 0o600)
    except Exception:
        pass


def fetch_user_id_from_token(token):
    """Busca IG_USER_ID automaticamente via GET /me para evitar erro manual."""
    data, err = _ig_get("/me", token)
    if data and "id" in data:
        return data["id"], data.get("username", "")
    return None, None


def run_smoke_tests(user_id, token):
    all_ok = True

    # Teste 1: /me → account_type=BUSINESS
    print("  Teste 1: Verificando conta Business...")
    data, err = _ig_get("/me", token)
    if err or not data:
        msg = err.get("error", {}).get("message", str(err)) if err else "sem resposta"
        print(f"  [FALHA] GET /me falhou: {msg}")
        all_ok = False
    else:
        acct = data.get("account_type", "")
        username = data.get("username", "")
        if acct == "BUSINESS":
            print(f"  [OK] Conta Business confirmada: @{username}")
        else:
            print(f"  [AVISO] account_type={acct!r} (esperado: BUSINESS)")
            all_ok = False

    # Teste 2: /me/media → ao menos 1 post
    print("  Teste 2: Verificando posts...")
    data2, err2 = _ig_get("/me/media", token)
    if err2 or not data2:
        msg = err2.get("error", {}).get("message", str(err2)) if err2 else "sem resposta"
        print(f"  [FALHA] GET /me/media falhou: {msg}")
        all_ok = False
        return all_ok, None, None
    else:
        posts = data2.get("data", [])
        if posts:
            media_id = posts[0]["id"]
            print(f"  [OK] {len(posts)} post(s) encontrado(s). Usando media_id={media_id}")
        else:
            print("  [AVISO] Nenhum post encontrado. Publique ao menos 1 post e tente novamente.")
            all_ok = False
            return all_ok, None, None

    # Teste 3: escopo comments
    print("  Teste 3: Verificando permissao de comentarios...")
    post_data, post_err = _ig_post(f"/{media_id}/comments", token, {"message": "teste-zxlab-apagar"})
    if post_err:
        code = post_err.get("error", {}).get("code", 0)
        msg = post_err.get("error", {}).get("message", str(post_err))
        print(f"  [FALHA] POST /{media_id}/comments falhou (code={code}): {msg}")
        all_ok = False
    else:
        comment_id = post_data.get("id")
        print(f"  [OK] Comentario criado: {comment_id}")
        if comment_id:
            del_data, del_err = _ig_delete(f"/{comment_id}", token)
            if del_err:
                print(f"  [AVISO] Nao foi possivel deletar comentario de teste: {del_err}")
            else:
                print("  [OK] Comentario de teste deletado.")

    # Teste 4: escopo messages
    print("  Teste 4: Verificando permissao de mensagens...")
    dm_data, dm_err = _ig_post(f"/{user_id}/messages", token, {
        "recipient": {"id": "FAKE_TEST_999"},
        "message": {"text": "teste-permissao"},
    })
    if dm_err:
        code = dm_err.get("error", {}).get("code", 0)
        msg = dm_err.get("error", {}).get("message", "")
        if code == 100:
            print("  [OK] Erro 100 (user not found) — permissao de mensagens OK.")
        elif code in (10, 200, 190):
            print(f"  [FALHA] Erro de permissao (code={code}): {msg}")
            print("  Verifique se o escopo instagram_business_manage_messages foi adicionado.")
            all_ok = False
        else:
            print(f"  [AVISO] Erro inesperado (code={code}): {msg}")
    else:
        print("  [OK] Endpoint de mensagens respondeu.")

    username = ""
    try:
        me_data, _ = _ig_get("/me", token)
        if me_data:
            username = me_data.get("username", "")
    except Exception:
        pass

    return all_ok, media_id, username


def collect_credentials():
    """Coleta credenciais e auto-preenche IG_USER_ID a partir do token."""
    print("  Agora cole as credenciais abaixo:")
    print()
    app_id = ask("IG_APP_ID_INSTAGRAM (App ID do Meta)")
    app_secret = ask("IG_APP_SECRET", secret=True)
    token = ask("IG_ACCESS_TOKEN", secret=True)

    if not all([app_id, app_secret, token]):
        return None, None, None, None, None

    # Auto-preencher IG_USER_ID
    print()
    print("  Buscando IG_USER_ID automaticamente via token...")
    auto_user_id, auto_username = fetch_user_id_from_token(token)
    if auto_user_id:
        print(f"  [OK] IG_USER_ID detectado: {auto_user_id} (@{auto_username})")
        user_id = auto_user_id
    else:
        print("  Nao foi possivel detectar automaticamente. Cole manualmente:")
        user_id = ask("IG_USER_ID (Instagram User ID)")

    return app_id, app_secret, user_id, token, auto_username


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [██░░░░░░░░] Etapa 2 de 10")
    print()
    print("  Etapa 2 — Criar App Meta + Gerar Token de Acesso")
    print()

    print("  Siga o passo a passo abaixo para criar o app Meta:")
    print()
    print("  1. Acesse: https://developers.facebook.com/apps")
    print("  2. Clique em 'Criar App'")
    print("     → Caso de uso: 'Gerenciar mensagens e conteudo no Instagram'")
    print()
    print("  3. Em 'Roles > Instagram Testers':")
    print("     → Adicione sua conta Instagram")
    print("     → Aceite o convite: Instagram > Configuracoes > Apps e Sites")
    print()
    print("  4. Adicione as 3 permissoes:")
    print("     → instagram_business_basic")
    print("     → instagram_business_manage_comments")
    print("     → instagram_business_manage_messages")
    print()
    print("  5. Clique em 'Gerar token' → OAuth popup → Autorize os 3 escopos")
    print()

    max_attempts = 3
    attempt = 0

    while attempt < max_attempts:
        app_id, app_secret, user_id, token, username = collect_credentials()

        if not all([app_id, app_secret, user_id, token]):
            print()
            print("  [ERRO] Todas as credenciais sao obrigatorias.")
            print()
            attempt += 1
            continue

        print()
        print("  Salvando credenciais em ~/.operacao-ia/config/instagram.env ...")
        save_env(app_id, app_secret, user_id, token)
        print("  [OK] instagram.env salvo.")
        print()

        print("  Executando smoke tests...")
        print()
        ok, media_id, smoke_username = run_smoke_tests(user_id, token)
        print()

        if ok:
            print("  [OK] Todos os smoke tests passaram!")
            break
        else:
            attempt += 1
            print("  Um ou mais testes falharam.")
            if attempt >= max_attempts:
                print(f"  [{attempt}/{max_attempts}] Limite de tentativas atingido.")
                print("  Verifique as instrucoes acima e execute esta etapa novamente.")
                mark_checkpoint("step_2_meta_app", "partial", "smoke_tests_failed")
                sys.exit(1)

            recoletar = ask(
                f"  Recolher credenciais e tentar novamente? ({attempt}/{max_attempts}) (s/N)",
                default="s",
            ).lower()
            if recoletar not in ("s", "sim", "y", "yes"):
                print("  Abortando. Execute novamente quando corrigir as credenciais.")
                mark_checkpoint("step_2_meta_app", "partial", "aborted_by_user")
                sys.exit(0)
            print()

    detail = f"user=@{username or smoke_username}" if (username or smoke_username) else f"user_id={user_id}"
    mark_checkpoint("step_2_meta_app", "done", detail)

    print("  [OK] Etapa 2 concluida!")
    print()
    print("  Proximo: python3 setup/setup_app_review.py")
    print()


if __name__ == "__main__":
    main()
