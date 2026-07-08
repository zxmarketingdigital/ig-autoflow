#!/usr/bin/env python3
"""
Mission Control Instagram — gera dashboard local do aluno com dados reais.

Le os logs dos 3 LaunchAgents (auto-responder, DM agent, token refresh) e
gera um HTML self-contained em ~/.operacao-ia/mission-control/instagram-dashboard.html

Uso:
    python3 ig_dashboard.py            # gera e imprime caminho
    python3 ig_dashboard.py --open     # gera e abre no navegador
"""

import html
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
from lib import (
    IG_ENV_PATH,
    IG_KB_PATH,
    IG_TRIGGERS_PATH,
    INSTAGRAM_DIR,
    MISSION_CONTROL_DIR,
    load_env_var,
    open_in_browser,
)

OUTPUT_PATH = MISSION_CONTROL_DIR / "instagram-dashboard.html"

AUTO_LOG = INSTAGRAM_DIR / "logs" / "ig-auto.log"
DM_LOG = INSTAGRAM_DIR / "logs" / "ig-dm.log"
TOKEN_LOG = INSTAGRAM_DIR / "logs" / "ig-token.log"


# ---------------------------------------------------------------------------
# Coleta de dados
# ---------------------------------------------------------------------------

def _read_log(path):
    p = Path(path)
    if not p.exists():
        return []
    try:
        return p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


def _parse_ts(line):
    # formato esperado: [2026-04-29T20:01:00] mensagem
    m = re.match(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]", line)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group(1))
    except Exception:
        return None


def _count_pattern(lines, pattern, hours=24):
    cutoff = datetime.now() - timedelta(hours=hours)
    count = 0
    for line in lines:
        if pattern not in line:
            continue
        ts = _parse_ts(line)
        if ts is None or ts >= cutoff:
            count += 1
    return count


def _last_run_ts(lines):
    for line in reversed(lines):
        ts = _parse_ts(line)
        if ts:
            return ts
    return None


def _last_log_line(lines, max_len=80):
    for line in reversed(lines):
        line = line.strip()
        if line:
            return line[:max_len]
    return "Sem logs ainda"


def _humanize_age(ts):
    if ts is None:
        return "nunca executou"
    delta = datetime.now() - ts
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"ha {secs}s"
    if secs < 3600:
        return f"ha {secs // 60}min"
    if secs < 86400:
        h = secs // 3600
        m = (secs % 3600) // 60
        return f"ha {h}h{m:02d}min"
    return f"ha {secs // 86400}d"


def _agent_status(label):
    """Verifica se o LaunchAgent esta carregado."""
    try:
        res = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode != 0:
            return "nao_carregado"
        return "carregado"
    except Exception:
        return "desconhecido"


def _token_info():
    generated = load_env_var(IG_ENV_PATH, "IG_TOKEN_GENERATED_AT") or ""
    if not generated:
        return None, None
    try:
        gen_dt = datetime.strptime(generated, "%Y-%m-%d")
        elapsed = (datetime.now() - gen_dt).days
        days_left = max(0, 60 - elapsed)
        return days_left, gen_dt
    except Exception:
        return None, None


def _load_triggers():
    p = Path(IG_TRIGGERS_PATH)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("triggers", [])
    except Exception:
        return []


def _load_products():
    p = Path(IG_KB_PATH)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("products", [])
    except Exception:
        return []


def _recent_errors(lines, limit=5):
    out = []
    for line in reversed(lines):
        if "[ERRO]" in line or "[ERROR]" in line:
            out.append(line.strip()[:140])
            if len(out) >= limit:
                break
    return out


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def _kpi_color(value, thresholds):
    """thresholds = (good_min, warn_min). Acima de good_min = verde."""
    if value >= thresholds[0]:
        return "green"
    if value >= thresholds[1]:
        return "amber"
    return "muted"


def render():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    auto_lines = _read_log(AUTO_LOG)
    dm_lines = _read_log(DM_LOG)
    token_lines = _read_log(TOKEN_LOG)

    # Comment Responder
    comments_24h = _count_pattern(auto_lines, "Private Reply DM enviada")
    auto_errors_24h = _count_pattern(auto_lines, "[ERRO]")
    auto_last_ts = _last_run_ts(auto_lines)
    auto_last_line = html.escape(_last_log_line(auto_lines))
    auto_status = _agent_status("com.zxlab.ig-auto")

    # DM Agent
    dms_24h = _count_pattern(dm_lines, "Resposta enviada")
    escalations_24h = _count_pattern(dm_lines, "Escalando")
    dm_errors_24h = _count_pattern(dm_lines, "[ERRO]")
    dm_last_ts = _last_run_ts(dm_lines)
    dm_last_line = html.escape(_last_log_line(dm_lines))
    dm_status = _agent_status("com.zxlab.ig-dm")

    # Token
    days_left, gen_dt = _token_info()
    token_last_ts = _last_run_ts(token_lines)
    token_status = _agent_status("com.zxlab.ig-token")

    # Config
    triggers = _load_triggers()
    products = _load_products()

    # Erros recentes
    auto_errs = _recent_errors(auto_lines)
    dm_errs = _recent_errors(dm_lines)

    # Status geral
    agents_loaded = sum(1 for s in [auto_status, dm_status, token_status] if s == "carregado")
    has_errors = (auto_errors_24h + dm_errors_24h) > 0
    token_critical = days_left is not None and days_left < 5

    if agents_loaded < 3 or token_critical:
        overall_cls, overall_label = "bad", "Atencao"
    elif has_errors:
        overall_cls, overall_label = "warn", "Operando com erros"
    else:
        overall_cls, overall_label = "ok", "Operacional"

    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ----- HTML helpers -----
    def status_pill(status):
        if status == "carregado":
            return '<span class="pill pill-ok">carregado</span>'
        if status == "nao_carregado":
            return '<span class="pill pill-bad">nao carregado</span>'
        return '<span class="pill pill-mute">desconhecido</span>'

    triggers_html = "".join(
        f'<tr><td><code>{html.escape(", ".join(str(k) for k in t.get("keywords", [])))}</code></td>'
        f'<td>{html.escape(str(t.get("reply_text") or "")[:60])}</td></tr>'
        for t in triggers
    ) or '<tr><td colspan="2" class="empty">Nenhum trigger configurado</td></tr>'

    products_html = "".join(
        f'<tr><td>{html.escape(str(p.get("nome", "?")))}</td>'
        f'<td class="mono">{html.escape(str(p.get("preco", "—")))}</td></tr>'
        for p in products
    ) or '<tr><td colspan="2" class="empty">Nenhum produto na base</td></tr>'

    auto_errs_html = "".join(f'<li class="mono">{html.escape(e)}</li>' for e in auto_errs) or '<li class="empty">Sem erros recentes</li>'
    dm_errs_html = "".join(f'<li class="mono">{html.escape(e)}</li>' for e in dm_errs) or '<li class="empty">Sem erros recentes</li>'

    token_color = "green" if days_left is None or days_left >= 30 else ("amber" if days_left >= 5 else "red")
    token_value = f"{days_left}d" if days_left is not None else "?"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mission Control Instagram — ZX Control</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0a0a0d;
    --surface: #12121a;
    --surface2: #1a1a26;
    --surface3: #232333;
    --border: #2a2a3d;
    --text: #ededf2;
    --text-dim: #8e8ea3;
    --text-mute: #5e5e72;
    --amber: #D97706;
    --amber-bright: #f59e0b;
    --amber-glow: rgba(217,119,6,0.15);
    --green: #10b981;
    --red: #ef4444;
    --yellow: #f59e0b;
    --blue: #60a5fa;
    --purple: #a78bfa;
    --pink: #ec4899;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg); color: var(--text);
    min-height: 100vh; line-height: 1.5;
  }}
  .mono {{ font-family: 'JetBrains Mono', monospace; font-size: 0.85em; }}
  code {{ font-family: 'JetBrains Mono', monospace; background: var(--surface3); padding: 1px 6px; border-radius: 4px; font-size: 0.85em; color: var(--amber-bright); }}

  .hero {{
    background: linear-gradient(135deg, var(--surface) 0%, #1a1410 100%);
    border-bottom: 1px solid var(--border);
    padding: 32px 40px 28px; position: relative; overflow: hidden;
  }}
  .hero::before {{
    content: ''; position: absolute; top: -50%; right: -10%;
    width: 600px; height: 600px;
    background: radial-gradient(circle, var(--amber-glow) 0%, transparent 60%);
    pointer-events: none;
  }}
  .hero-row {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; position: relative; z-index: 1; }}
  .hero-title h1 {{
    font-size: 28px; font-weight: 800; letter-spacing: -0.02em;
    background: linear-gradient(135deg, #fff 30%, var(--amber-bright));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }}
  .hero-title .subtitle {{
    color: var(--text-dim); font-size: 13px; margin-top: 4px; font-weight: 500;
    letter-spacing: 0.04em; text-transform: uppercase;
  }}
  .hero-status {{
    display: flex; align-items: center; gap: 10px;
    background: var(--surface2); border: 1px solid var(--border);
    padding: 10px 16px; border-radius: 10px;
  }}
  .hero-status .pulse {{ width: 10px; height: 10px; border-radius: 50%; }}
  .hero-status.ok .pulse {{ background: var(--green); animation: pulse 2s infinite; }}
  .hero-status.warn .pulse {{ background: var(--yellow); animation: pulse 2s infinite; }}
  .hero-status.bad .pulse {{ background: var(--red); animation: pulse 1s infinite; }}
  @keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 currentColor; }}
    70%  {{ box-shadow: 0 0 0 10px transparent; }}
    100% {{ box-shadow: 0 0 0 0 transparent; }}
  }}
  .hero-status .label {{ font-weight: 600; font-size: 14px; }}
  .hero-status.ok .label {{ color: var(--green); }}
  .hero-status.warn .label {{ color: var(--yellow); }}
  .hero-status.bad .label {{ color: var(--red); }}
  .hero-meta {{ color: var(--text-mute); font-size: 12px; margin-top: 4px; text-align: right; }}

  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 28px; position: relative; z-index: 1; }}
  .kpi {{
    background: var(--surface2); border: 1px solid var(--border);
    padding: 18px 20px; border-radius: 12px; transition: all 0.2s;
  }}
  .kpi:hover {{ border-color: var(--amber); transform: translateY(-2px); }}
  .kpi .label {{ font-size: 11px; text-transform: uppercase; color: var(--text-dim); letter-spacing: 0.06em; font-weight: 600; }}
  .kpi .value {{ font-size: 32px; font-weight: 700; margin-top: 6px; letter-spacing: -0.02em; }}
  .kpi .sub {{ font-size: 12px; color: var(--text-dim); margin-top: 4px; font-family: 'JetBrains Mono', monospace; }}
  .kpi.amber .value {{ color: var(--amber-bright); }}
  .kpi.green .value {{ color: var(--green); }}
  .kpi.blue .value {{ color: var(--blue); }}
  .kpi.purple .value {{ color: var(--purple); }}
  .kpi.red .value {{ color: var(--red); }}
  .kpi.muted .value {{ color: var(--text-mute); }}

  .container {{ max-width: 1400px; margin: 0 auto; padding: 32px 40px 60px; }}
  .grid {{ display: grid; gap: 20px; }}
  .grid-2 {{ grid-template-columns: 1fr 1fr; }}
  .grid-3 {{ grid-template-columns: 1fr 1fr 1fr; }}

  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 24px;
  }}
  .card-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--border);
  }}
  .card-header h2 {{
    font-size: 16px; font-weight: 700; letter-spacing: -0.01em;
    display: flex; align-items: center; gap: 10px;
  }}
  .card-header h2::before {{
    content: ''; width: 3px; height: 16px; background: var(--amber); border-radius: 2px;
  }}
  .card-header .badge {{
    background: var(--amber-glow); color: var(--amber-bright);
    padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
  }}

  /* Agent cards */
  .agent {{
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 12px; padding: 18px 20px;
    border-left: 3px solid var(--text-mute);
  }}
  .agent.ok {{ border-left-color: var(--green); }}
  .agent.warn {{ border-left-color: var(--yellow); }}
  .agent.bad {{ border-left-color: var(--red); }}
  .agent-head {{
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
  }}
  .agent-name {{ font-size: 14px; font-weight: 700; }}
  .agent-name .icon {{ font-size: 16px; margin-right: 6px; }}
  .agent-metrics {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }}
  .am {{ background: var(--surface); border-radius: 8px; padding: 10px 12px; border: 1px solid var(--border); }}
  .am-num {{ font-size: 20px; font-weight: 700; line-height: 1; }}
  .am.green .am-num {{ color: var(--green); }}
  .am.amber .am-num {{ color: var(--amber-bright); }}
  .am.red .am-num {{ color: var(--red); }}
  .am.muted .am-num {{ color: var(--text-mute); }}
  .am-lbl {{ font-size: 10px; text-transform: uppercase; color: var(--text-dim); margin-top: 4px; letter-spacing: 0.04em; font-weight: 600; }}
  .agent-foot {{ font-size: 11px; color: var(--text-dim); padding-top: 10px; border-top: 1px dashed var(--border); }}
  .agent-foot .mono {{ color: var(--text-mute); display: block; margin-top: 4px; word-break: break-all; }}

  /* Pills */
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; font-family: 'JetBrains Mono', monospace; }}
  .pill-ok {{ background: rgba(16,185,129,0.18); color: var(--green); }}
  .pill-bad {{ background: rgba(239,68,68,0.18); color: var(--red); }}
  .pill-mute {{ background: var(--surface3); color: var(--text-mute); }}

  /* Tables */
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--text-dim); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }}
  td.empty {{ text-align: center; color: var(--text-mute); padding: 20px; }}

  /* Lists */
  ul.errors {{ list-style: none; padding: 0; }}
  ul.errors li {{ background: rgba(239,68,68,0.06); border-left: 3px solid var(--red); padding: 8px 12px; margin-bottom: 6px; border-radius: 0 6px 6px 0; font-size: 12px; word-break: break-all; }}
  ul.errors li.empty {{ background: rgba(16,185,129,0.06); border-left-color: var(--green); color: var(--green); }}

  /* Quick commands */
  .commands {{ display: grid; gap: 12px; }}
  .cmd-block {{
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px;
  }}
  .cmd-block .cmd-title {{ font-size: 12px; color: var(--text-dim); margin-bottom: 6px; font-weight: 600; }}
  .cmd-block code {{ display: block; background: var(--bg); padding: 8px 10px; border-radius: 6px; font-size: 11px; color: var(--amber-bright); user-select: all; }}

  footer {{
    text-align: center; color: var(--text-mute); font-size: 11px;
    padding: 30px 0 10px; font-family: 'JetBrains Mono', monospace;
  }}
  footer a {{ color: var(--amber); text-decoration: none; }}

  @media (max-width: 1100px) {{
    .kpis {{ grid-template-columns: repeat(2,1fr); }}
    .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
    .hero {{ padding: 24px; }}
    .container {{ padding: 24px 20px 40px; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-row">
    <div class="hero-title">
      <h1>Mission Control Instagram</h1>
      <div class="subtitle">ZX Control · Semana 5 · Automacao Instagram</div>
    </div>
    <div>
      <div class="hero-status {overall_cls}">
        <div class="pulse"></div>
        <div class="label">{overall_label}</div>
      </div>
      <div class="hero-meta mono">atualizado · {now}</div>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi {'green' if comments_24h > 0 else 'muted'}">
      <div class="label">Comentarios respondidos · 24h</div>
      <div class="value">{comments_24h}</div>
      <div class="sub">{auto_errors_24h} erros</div>
    </div>
    <div class="kpi {'green' if dms_24h > 0 else 'muted'}">
      <div class="label">DMs respondidas · 24h</div>
      <div class="value">{dms_24h}</div>
      <div class="sub">{escalations_24h} escalacoes · {dm_errors_24h} erros</div>
    </div>
    <div class="kpi {token_color}">
      <div class="label">Token expira em</div>
      <div class="value">{token_value}</div>
      <div class="sub">{f'gerado {gen_dt.strftime("%d/%m/%Y")}' if gen_dt else 'token nao detectado'}</div>
    </div>
    <div class="kpi {'green' if agents_loaded == 3 else ('amber' if agents_loaded > 0 else 'red')}">
      <div class="label">Agentes carregados</div>
      <div class="value">{agents_loaded}<span style="color:var(--text-mute);font-size:18px">/3</span></div>
      <div class="sub">launchctl status</div>
    </div>
  </div>
</div>

<div class="container">

  <div class="grid grid-3" style="margin-bottom: 20px">
    <div class="agent {'ok' if auto_status == 'carregado' and auto_errors_24h == 0 else ('warn' if auto_status == 'carregado' else 'bad')}">
      <div class="agent-head">
        <div class="agent-name"><span class="icon">💬</span>Comment Responder</div>
        {status_pill(auto_status)}
      </div>
      <div class="agent-metrics">
        <div class="am green">
          <div class="am-num">{comments_24h}</div>
          <div class="am-lbl">Respondidos 24h</div>
        </div>
        <div class="am {'red' if auto_errors_24h > 0 else 'muted'}">
          <div class="am-num">{auto_errors_24h}</div>
          <div class="am-lbl">Erros 24h</div>
        </div>
      </div>
      <div class="agent-foot">
        Ultimo run: <strong>{_humanize_age(auto_last_ts)}</strong>
        <span class="mono">{auto_last_line}</span>
      </div>
    </div>

    <div class="agent {'ok' if dm_status == 'carregado' and dm_errors_24h == 0 else ('warn' if dm_status == 'carregado' else 'bad')}">
      <div class="agent-head">
        <div class="agent-name"><span class="icon">📨</span>DM Agent</div>
        {status_pill(dm_status)}
      </div>
      <div class="agent-metrics">
        <div class="am green">
          <div class="am-num">{dms_24h}</div>
          <div class="am-lbl">Respondidas 24h</div>
        </div>
        <div class="am amber">
          <div class="am-num">{escalations_24h}</div>
          <div class="am-lbl">Escalacoes 24h</div>
        </div>
        <div class="am {'red' if dm_errors_24h > 0 else 'muted'}">
          <div class="am-num">{dm_errors_24h}</div>
          <div class="am-lbl">Erros 24h</div>
        </div>
        <div class="am muted">
          <div class="am-num" style="font-size:13px">{_humanize_age(dm_last_ts)}</div>
          <div class="am-lbl">Ultimo run</div>
        </div>
      </div>
      <div class="agent-foot">
        <span class="mono">{dm_last_line}</span>
      </div>
    </div>

    <div class="agent {'ok' if token_status == 'carregado' and (days_left is None or days_left > 5) else 'bad'}">
      <div class="agent-head">
        <div class="agent-name"><span class="icon">🔑</span>Token Refresh</div>
        {status_pill(token_status)}
      </div>
      <div class="agent-metrics">
        <div class="am {token_color}">
          <div class="am-num">{token_value}</div>
          <div class="am-lbl">Dias restantes</div>
        </div>
        <div class="am muted">
          <div class="am-num" style="font-size:13px">{_humanize_age(token_last_ts)}</div>
          <div class="am-lbl">Ultimo refresh</div>
        </div>
      </div>
      <div class="agent-foot">
        Renova diariamente as 03h<br>
        <span class="mono">Token gerado {gen_dt.strftime('%d/%m/%Y') if gen_dt else '—'}</span>
      </div>
    </div>
  </div>

  <div class="grid grid-2" style="margin-bottom: 20px">
    <div class="card">
      <div class="card-header">
        <h2>Triggers configurados</h2>
        <span class="badge">{len(triggers)} regras</span>
      </div>
      <table>
        <thead><tr><th>Keywords</th><th>Resposta</th></tr></thead>
        <tbody>{triggers_html}</tbody>
      </table>
    </div>

    <div class="card">
      <div class="card-header">
        <h2>Knowledge Base · Produtos</h2>
        <span class="badge">{len(products)} itens</span>
      </div>
      <table>
        <thead><tr><th>Produto</th><th style="text-align:right">Preco</th></tr></thead>
        <tbody>{products_html}</tbody>
      </table>
    </div>
  </div>

  <div class="grid grid-2" style="margin-bottom: 20px">
    <div class="card">
      <div class="card-header">
        <h2>Erros recentes · Comment Responder</h2>
        <span class="badge" style="background:{'rgba(239,68,68,0.15)' if auto_errs else 'rgba(16,185,129,0.15)'}; color:{'var(--red)' if auto_errs else 'var(--green)'}">{len(auto_errs)}</span>
      </div>
      <ul class="errors">{auto_errs_html}</ul>
    </div>

    <div class="card">
      <div class="card-header">
        <h2>Erros recentes · DM Agent</h2>
        <span class="badge" style="background:{'rgba(239,68,68,0.15)' if dm_errs else 'rgba(16,185,129,0.15)'}; color:{'var(--red)' if dm_errs else 'var(--green)'}">{len(dm_errs)}</span>
      </div>
      <ul class="errors">{dm_errs_html}</ul>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <h2>Comandos rapidos</h2>
      <span class="badge">copie &amp; cole</span>
    </div>
    <div class="commands">
      <div class="cmd-block">
        <div class="cmd-title">Forcar Comment Responder agora</div>
        <code>launchctl kickstart -k gui/$(id -u)/com.zxlab.ig-auto</code>
      </div>
      <div class="cmd-block">
        <div class="cmd-title">Forcar DM Agent agora</div>
        <code>launchctl kickstart -k gui/$(id -u)/com.zxlab.ig-dm</code>
      </div>
      <div class="cmd-block">
        <div class="cmd-title">Ver log do Comment Responder em tempo real</div>
        <code>tail -f {AUTO_LOG}</code>
      </div>
      <div class="cmd-block">
        <div class="cmd-title">Ver log do DM Agent em tempo real</div>
        <code>tail -f {DM_LOG}</code>
      </div>
      <div class="cmd-block">
        <div class="cmd-title">Atualizar este dashboard manualmente</div>
        <code>python3 {Path(__file__).resolve()}</code>
      </div>
    </div>
  </div>

</div>

<footer>
  Mission Control Instagram · ZX Control Semana 5 · Gerado em {now}<br>
  <a href="https://zxlab.com.br/mission-control">zxlab.com.br/mission-control</a>
</footer>

</body>
</html>"""

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    return OUTPUT_PATH


def main():
    path = render()
    print(f"OK Dashboard gerado: {path}")
    if "--open" in sys.argv:
        open_in_browser(path)
        print("OK Aberto no navegador")


if __name__ == "__main__":
    main()
