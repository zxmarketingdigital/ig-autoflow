# Testes Manuais — ig-autoflow

Guia para rodar, depurar e validar cada automação de forma independente, sem depender do LaunchAgent.

---

## 1. Rodar o Comment Responder standalone

```bash
# Modo real (envia replies + DMs)
python3 ~/.operacao-ia/scripts/instagram/ig_auto_responder.py

# Dry-run (simula sem enviar nada)
python3 ~/.operacao-ia/scripts/instagram/ig_auto_responder.py --dry-run

# Status (comentários processados + última linha do log)
python3 ~/.operacao-ia/scripts/instagram/ig_auto_responder.py --status
```

**O que esperar no dry-run:**
```
[2026-04-30T10:00:00] Posts com comentarios encontrados: 12 (limite scan=100, processar=50)
[2026-04-30T10:00:01] Keyword detectada: 'quero saber mais' | comment_id=17855...
[2026-04-30T10:00:01]   [DRY-RUN] Dispararia reply + DM para comment_id=17855...
[2026-04-30T10:00:02] Ciclo concluido. 0 comentarios processados.
```

---

## 2. Simular comentário via curl (teste de permissão)

Substitua `MEDIA_ID` e `TOKEN`:

```bash
# Postar comentário de teste
curl -X POST \
  "https://graph.instagram.com/v22.0/MEDIA_ID/comments" \
  -d "message=testeKeyword&access_token=TOKEN"

# Deletar comentário de teste (substituir COMMENT_ID)
curl -X DELETE \
  "https://graph.instagram.com/v22.0/COMMENT_ID?access_token=TOKEN"
```

---

## 3. Verificar logs do LaunchAgent

```bash
# Comment Responder
tail -50 ~/.operacao-ia/scripts/instagram/logs/ig-auto.log

# DM Agent
tail -50 ~/.operacao-ia/scripts/instagram/logs/ig-dm.log

# Token Refresh
tail -50 ~/.operacao-ia/scripts/instagram/logs/ig-token.log

# Seguir em tempo real
tail -f ~/.operacao-ia/scripts/instagram/logs/ig-auto.log
```

---

## 4. Forçar execução via launchctl kickstart

```bash
# Descobrir seu UID (geralmente 501 no macOS)
id -u

# Forçar execução imediata (substitua UID)
launchctl kickstart -k gui/501/com.zxlab.ig-auto
launchctl kickstart -k gui/501/com.zxlab.ig-dm
launchctl kickstart -k gui/501/com.zxlab.ig-token

# Verificar se LaunchAgent está carregado
launchctl list | grep zxlab

# Verificar detalhes de um agent específico
launchctl list com.zxlab.ig-auto
```

---

## 5. Por que `sleep + comando` é bloqueado no Claude CLI

O Claude CLI (Claude Code) bloqueia comandos com `sleep` longo por segurança — ele não pode aguardar indefinidamente por um processo em background.

**Solução para testar via Claude:** use sempre `--dry-run` ou execução direta:
```bash
# Não fazer (bloqueado):
# sleep 30 && tail -5 logs/ig-auto.log

# Fazer (funciona):
python3 ~/.operacao-ia/scripts/instagram/ig_auto_responder.py --dry-run
```

---

## 6. Variáveis de ambiente úteis

```bash
# Aumentar cobertura de posts
IG_POSTS_SCAN_LIMIT=200 python3 ~/.operacao-ia/scripts/instagram/ig_auto_responder.py --dry-run

# Processar mais posts por ciclo
IG_POSTS_PROCESS_MAX=100 python3 ~/.operacao-ia/scripts/instagram/ig_auto_responder.py --dry-run

# Aumentar cobertura de conversas DM
IG_CONVS_SCAN_LIMIT=100 python3 ~/.operacao-ia/scripts/instagram/ig_dm_agent.py
```

---

## 7. Diagnóstico rápido pós-instalação

```bash
# Auditoria de 11 checks (sem runtime)
python3 setup/setup_audit_s5.py

# Auditoria com disparo end-to-end
python3 setup/setup_audit_s5.py --with-runtime

# Corrigir schemas automaticamente
python3 setup/setup_audit_s5.py --fix

# Smoke test de runtime (check #12 opt-in)
python3 scripts/smoke_test_runtime.py
```

---

## 8. Verificar token Instagram

```bash
TOKEN=$(grep IG_ACCESS_TOKEN ~/.operacao-ia/config/instagram.env | cut -d= -f2)
curl -s "https://graph.instagram.com/v22.0/me?access_token=$TOKEN" | python3 -m json.tool
```

**Token válido retorna:**
```json
{
  "id": "17841...",
  "username": "seu_usuario",
  "account_type": "BUSINESS"
}
```

---

## 9. Estrutura de arquivos pós-setup

```
~/.operacao-ia/
├── config/
│   ├── instagram.env        # IG_ACCESS_TOKEN, IG_USER_ID, ANTHROPIC_API_KEY
│   └── week5_checkpoint.json
└── scripts/
    └── instagram/
        ├── ig_auto_responder.py   # Comment Responder
        ├── ig_dm_agent.py         # DM Agent
        ├── ig_token_refresh.py    # Token Refresh
        ├── ig_triggers.json       # Keywords configuradas
        ├── ig_kb.json             # Base de conhecimento (produtos)
        ├── ig_state.json          # IDs de comentários já processados
        ├── ig_dm_sessions.sqlite  # Conversas DM rastreadas
        ├── lib.py                 # Utilitários
        ├── ig_schemas.py          # Schemas e validators
        └── logs/
            ├── ig-auto.log
            ├── ig-dm.log
            └── ig-token.log

~/Library/LaunchAgents/
├── com.zxlab.ig-auto.plist    # Roda a cada 30min
├── com.zxlab.ig-dm.plist      # Roda a cada 5min
└── com.zxlab.ig-token.plist   # Roda às 03h diariamente
```
