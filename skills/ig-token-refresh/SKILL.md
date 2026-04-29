---
name: ig-token-refresh
description: "Renova o token de acesso do Instagram antes de expirar. Use quando o token estiver com menos de 10 dias para expirar ou quando o aluno reportar erros de autenticação no Instagram."
model: haiku
effort: low
---

# ig-token-refresh

Renova o long-lived token do Instagram (válido por 60 dias).

## Quando usar

- Token com menos de 10 dias para expirar
- Erros 401/190 nas chamadas à API
- Após update manual de credenciais

## Como executar

```bash
python3 ~/.operacao-ia/scripts/instagram/ig_token_refresh.py
```

O script lê o token atual de `~/.operacao-ia/config/instagram.env`, chama o endpoint de refresh e atualiza o arquivo automaticamente.

## Endpoint de refresh

```
GET https://graph.instagram.com/refresh_access_token
  ?grant_type=ig_refresh_token
  &access_token={IG_ACCESS_TOKEN}
```
