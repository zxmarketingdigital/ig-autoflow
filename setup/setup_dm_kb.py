#!/usr/bin/env python3
"""
Etapa 5 — DM Knowledge Base
Cadastrar produtos/servicos que o agente de DM vai usar para responder.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from lib import (
    IG_KB_PATH,
    INSTAGRAM_DIR,
    mark_checkpoint,
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


def ask_multiline(prompt):
    print(f"  {prompt} (Enter duplo para finalizar):")
    lines = []
    try:
        while True:
            line = input("  > ")
            if not line and lines and not lines[-1]:
                lines.pop()
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        print()
        print("  Setup cancelado.")
        sys.exit(0)
    return "\n".join(lines).strip()


def collect_products():
    produtos = []

    try:
        qty_str = ask("Quantos produtos quer cadastrar?", default="1")
        qty = int(qty_str) if qty_str.isdigit() else 1
    except Exception:
        qty = 1

    for i in range(1, qty + 1):
        print()
        print(f"  --- Produto #{i} ---")
        nome = ask(f"Nome do produto #{i}")
        url = ask(f"URL/link do produto #{i}")
        descricao = ask_multiline(f"Descricao/diferencial do produto #{i}")
        preco = ask(f"Preco do produto #{i} (ex: R$ 497,00)")
        bonus = ask(f"Bonus do produto #{i} (opcional, Enter para pular)", default="")

        produtos.append({
            "nome": nome,
            "url": url,
            "descricao": descricao,
            "preco": preco,
            "bonus": bonus,
        })
        print(f"  [OK] Produto '{nome}' cadastrado.")

    return produtos


def preview_products(produtos):
    print()
    print("  Preview da base de conhecimento:")
    print()
    for i, p in enumerate(produtos, 1):
        print(f"  [{i}] {p['nome']}")
        print(f"      Preco: {p['preco']}")
        print(f"      Link: {p['url']}")
        if p.get("bonus"):
            print(f"      Bonus: {p['bonus']}")
        desc_preview = p["descricao"][:80].replace("\n", " ")
        if desc_preview:
            print(f"      Descricao: {desc_preview}{'...' if len(p['descricao']) > 80 else ''}")
        print()


def save_kb(produtos):
    INSTAGRAM_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# ig_knowledge_base.py",
        "# Gerado automaticamente pelo setup da Semana 5.",
        "# Edite para atualizar seus produtos/servicos.",
        "",
        "PRODUTOS = [",
    ]
    for p in produtos:
        descricao_escaped = p["descricao"].replace('"""', "'''")
        lines.append("    {")
        lines.append(f'        "nome": {repr(p["nome"])},')
        lines.append(f'        "url": {repr(p["url"])},')
        lines.append(f'        "preco": {repr(p["preco"])},')
        lines.append(f'        "bonus": {repr(p["bonus"])},')
        lines.append(f'        "descricao": """{descricao_escaped}""",')
        lines.append("    },")
    lines.append("]")
    lines.append("")

    IG_KB_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [OK] ig_knowledge_base.py salvo em {INSTAGRAM_DIR}")


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   ZX Control — Semana 5: Automacao Instagram         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  [█████░░░░░] Etapa 5 de 10")
    print()
    print("  Etapa 5 — DM Knowledge Base")
    print()
    print("  Cadastre os produtos/servicos que o agente de DM vai usar")
    print("  para responder automaticamente aos seus seguidores.")
    print()

    produtos = collect_products()

    preview_products(produtos)

    confirmar = ask("Confirmar e salvar? (s/N)", default="N").lower()
    if confirmar not in ("s", "sim", "y", "yes"):
        print("  Cadastro cancelado. Execute novamente para recadastrar.")
        sys.exit(0)

    save_kb(produtos)

    count = len(produtos)
    mark_checkpoint("step_5_dm_kb", "done", f"produtos={count}")

    print()
    print("  [OK] Etapa 5 concluida!")
    print()
    print("  Proximo: python3 setup/setup_dm_agent.py")
    print()


if __name__ == "__main__":
    main()
