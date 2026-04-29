#!/usr/bin/env python3
"""
Etapa 7 — Mission Control 5.0
Adiciona widgets de Instagram ao dashboard e atualiza titulo.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    INSTAGRAM_DIR,
    mark_checkpoint,
    now_iso,
)

MISSION_CONTROL_DIR = Path.home() / ".zxlab-mission-control"
DASHBOARD_CANDIDATES = [
    MISSION_CONTROL_DIR / "dashboard.html",
    Path.home() / ".operacao-ia" / "mission-control" / "dashboard.html",
]

IG_AUTO_LOG = INSTAGRAM_DIR / "logs" / "ig-auto.log"
IG_DM_LOG = INSTAGRAM_DIR / "logs" / "ig-dm.log"
IG_TOKEN_LOG = INSTAGRAM_DIR / "logs" / "ig-token.log"


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


def find_dashboard():
    for candidate in DASHBOARD_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def read_last_log_line(log_path):
    if not Path(log_path).exists():
        return "sem log"
    try:
        lines = Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        return lines[-1][:120] if lines else "sem entradas"
    except Exception:
        return "erro ao ler log"


def count_log_entries(log_path, keyword):
    if not Path(log_path).exists():
        return 0
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
        return text.count(keyword)
    except Exception:
        return 0


def read_token_age():
    from lib import IG_ENV_PATH, load_env_var
    token = load_env_var(IG_ENV_PATH, "IG_ACCESS_TOKEN")
    if not token:
        return None
    token_log = Path(IG_TOKEN_LOG)
    if token_log.exists():
        try:
            lines = token_log.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in reversed(lines):
                if "expires_in" in line.lower() or "dias" in line.lower():
                    return line[:80]
        except Exception:
            pass
    return "desconhecido"


def build_widgets_html():
    ts = datetime.now(timezone.utc).strftime("%d/%m %H:%M")
    auto_last = read_last_log_line(IG_AUTO_LOG)
    auto_comments = count_log_entries(IG_AUTO_LOG, "comment_id")
    auto_errors = count_log_entries(IG_AUTO_LOG, "ERRO") + count_log_entries(IG_AUTO_LOG, "FALHA")

    dm_last = read_last_log_line(IG_DM_LOG)
    dm_replies = count_log_entries(IG_DM_LOG, "dm_respondida")
    dm_escalacoes = count_log_entries(IG_DM_LOG, "escalacao")

    token_age = read_token_age() or "verificar"

    widgets = f"""
<!-- ZX Control S5 Widgets — gerado em {ts} -->
<div class="zx-widget" id="widget-ig-auto">
  <h3>IG Auto-Responder</h3>
  <p>Ultimo run: {auto_last[:60]}</p>
  <p>Comentarios processados: {auto_comments}</p>
  <p>Falhas: {auto_errors}</p>
</div>
<div class="zx-widget" id="widget-ig-dm">
  <h3>IG DM Agent</h3>
  <p>Ultimo run: {dm_last[:60]}</p>
  <p>DMs respondidas: {dm_replies}</p>
  <p>Escalacoes: {dm_escalacoes}</p>
</div>
<div class="zx-widget {"zx-widget--alert" if isinstance(token_age, str) and "desconhecido" not in token_age else ""}" id="widget-ig-token">
  <h3>IG Token Age</h3>
  <p>Status: {token_age}</p>
</div>
"""
    return widgets


def patch_dashboard(dashboard_path, widgets_html):
    content = dashboard_path.read_text(encoding="utf-8")

    # Atualiza titulo para Mission Control 5.0
    if "Mission Control 4.0" in content:
        content = content.replace("Mission Control 4.0", "Mission Control 5.0")
        print("  [OK] Titulo atualizado para Mission Control 5.0")
    elif "Mission Control" in content and "5.0" not in content:
        import re
        content = re.sub(r"Mission Control \d+\.\d+", "Mission Control 5.0", content)
        print("  [OK] Titulo atualizado para Mission Control 5.0")

    # Remove widgets S5 anteriores se existirem
    start_marker = "<!-- ZX Control S5 Widgets"
    end_marker = "<!-- /ZX Control S5 Widgets -->"
    if start_marker in content:
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)
        if end_idx > start_idx:
            content = content[:start_idx] + content[end_idx + len(end_marker):]

    # Insere widgets antes de </body>
    if "</body>" in content:
        content = content.replace("</body>", widgets_html + "\n<!-- /ZX Control S5 Widgets -->\n</body>")
        print("  [OK] Widgets IG inseridos no dashboard.")
    else:
        content += widgets_html + "\n<!-- /ZX Control S5 Widgets -->"
        print("  [OK] Widgets IG adicionados ao final do dashboard.")

    dashboard_path.write_text(content, encoding="utf-8")


def create_minimal_dashboard(path):
    ts = now_iso()
    content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Mission Control 5.0</title>
  <style>
    body {{ font-family: 'Inter', sans-serif; background: #0a0a0a; color: #f0f0f0; padding: 2rem; }}
    .zx-widget {{ background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
    .zx-widget h3 {{ color: #D97706; margin: 0 0 .5rem; }}
    .zx-widget--alert {{ border-color: #ef4444; }}
  </style>
</head>
<body>
  <h1>Mission Control 5.0</h1>
  <p>Gerado em: {ts}</p>
</body>
</html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  [OK] Dashboard criado em: {path}")


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [███████░░░] Etapa 7 de 10")
    print()
    print("  Etapa 7 — Mission Control 5.0")
    print()

    dashboard_path = find_dashboard()

    if dashboard_path:
        print(f"  Dashboard encontrado: {dashboard_path}")
    else:
        print("  Dashboard nao encontrado. Criando dashboard minimo...")
        dashboard_path = MISSION_CONTROL_DIR / "dashboard.html"
        create_minimal_dashboard(dashboard_path)

    print("  Coletando dados dos agentes Instagram...")
    widgets_html = build_widgets_html()
    print("  [OK] Dados coletados.")
    print()

    print("  Atualizando dashboard...")
    patch_dashboard(dashboard_path, widgets_html)
    print()

    print(f"  Dashboard atualizado: {dashboard_path}")
    print()

    mark_checkpoint("step_7_mission_update", "done", f"dashboard={dashboard_path}")

    print("  [OK] Etapa 7 concluida!")
    print()
    print("  Proximo: python3 setup/setup_audit_s5.py")
    print()


if __name__ == "__main__":
    main()
