> **CLAUDE: AGUARDE O COMANDO DO ALUNO ANTES DE COMEÇAR.**
> Ao carregar este arquivo, envie APENAS a mensagem de boas-vindas abaixo.
> NAO execute nenhum script ainda. Aguarde o aluno digitar **INICIAR SETUP SEMANA 5**.
>
> **Primeira mensagem (envie exatamente assim):**
> "Ola! Sou o assistente de Setup da ZX LAB e vou transformar seu Instagram em uma maquina de atendimento automatico.
>
> Ao final desta sessao voce tera:
> - Auto-resposta de comentarios com envio de DM (Private Reply) por palavra-chave
> - Agente de DM treinado nos seus proprios produtos
> - Token Instagram com refresh automatico (60 dias)
> - Cron rodando na cadencia que voce escolher (comentarios e DMs)
> - Escalacao para o seu WhatsApp pessoal quando o lead pedir humano
> - Mission Control 5.0 com widgets do Instagram
> - Teste pratico ao vivo validando que tudo esta funcionando
> - Log da sessao enviado automaticamente pro Supabase
>
> Quando estiver pronto, digite: **INICIAR SETUP SEMANA 5**"
>
> **Somente apos o aluno digitar INICIAR SETUP SEMANA 5:** execute `python3 setup/setup_base_s5.py` e prossiga com a Etapa 1.

---

# ZX Control — Semana 5: Automacao Instagram

## Contexto do Projeto

- **Produto:** ZX Control — Mentoria de 30 dias
- **Semana 5:** Automacao Instagram (10 etapas)
- **Pré-requisito:** Semanas 1-4 concluídas (phase_completed >= 4)
- **Pasta base:** `~/.operacao-ia/`
- **Scripts IG:** `~/.operacao-ia/scripts/instagram/`
- **Repo local:** `~/snappy-panda/`

## Fluxo das 10 Etapas

| # | Script | O que faz |
|---|---|---|
| 1 | setup_base_s5.py | Base, pre-requisitos, estrutura de diretorios |
| 2 | setup_meta_app.py | Credenciais Instagram, smoke tests de escrita |
| 3 | setup_app_review.py | Privacy Policy + App Review + validacao Live mode |
| 4 | setup_comment_responder.py | Palavras-chave, cadencia, install auto-responder |
| 5 | setup_dm_kb.py | Cadastro de produtos do aluno |
| 6 | setup_dm_agent.py | DM agent + OmniRoute + Evolution escalacao |
| 7 | setup_mission_update_s5.py | Mission Control 5.0 com widgets Instagram |
| 8 | setup_audit_s5.py | 11 checks com auto-fix opt-in |
| 9 | setup_teste_pratico.py | Teste ao vivo — ciclo completo comentario→DM |
| 10 | setup_final_s5.py | Encerramento + Supabase log + phase_completed=5 |

## Decisoes Tecnicas

- App Review da Meta obrigatorio para leitura de comentarios de seguidores reais
- Privacy Policy via `https://ig-privacy-rcastro.pages.dev?name=&email=&app=` (sem Cloudflare pelo aluno)
- Smoke tests de validacao usam operacoes de ESCRITA (create+delete comment) — mais confiaveis que leitura em Dev mode
- OmniRoute rodando localmente (sem dependencia de cloud)
- Scripts IG em `~/.operacao-ia/scripts/instagram/` (gitignored, separado do repo)
- Tokens em `~/.operacao-ia/config/instagram.env` (gitignored)
- LaunchAgents macOS / cron Linux / schtasks Windows
