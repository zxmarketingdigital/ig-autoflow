---
name: ig-status
description: "Verifica status dos agentes Instagram (auto-responder e DM agent): último run, comentários processados, DMs respondidas, dias até expirar o token. Use quando o usuario perguntar sobre o Instagram ou status dos agentes."
model: haiku
effort: low
---

# ig-status

Verifica o status dos agentes de automação Instagram instalados em `~/.operacao-ia/scripts/instagram/`.

## O que verifica

1. **Token**: dias até expirar (lê IG_TOKEN_GENERATED_AT de instagram.env)
2. **ig_auto_responder**: último run nos logs, comentários processados nas últimas 24h
3. **ig_dm_agent**: último run, DMs respondidas, escalações
4. **LaunchAgents**: se ig-auto e ig-dm estão carregados

## Como executar

```bash
python3 ~/.operacao-ia/scripts/instagram/ig_auto_responder.py --status
python3 ~/.operacao-ia/scripts/instagram/ig_dm_agent.py --status
launchctl list | grep zxlab
```
