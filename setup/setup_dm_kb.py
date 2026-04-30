#!/usr/bin/env python3
"""
Etapa 5 — DM Knowledge Base
Cadastrar produtos/servicos que o agente de DM vai usar para responder.
"""

import json
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
from ig_schemas import validate_products, make_product


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


def ask_url(prompt):
    while True:
        value = ask(prompt)
        if not value:
            print("  URL e obrigatoria. Digite novamente.")
            continue
        if not (value.startswith("http://") or value.startswith("https://")):
            confirm = ask(f"  '{value}' nao parece uma URL. Usar mesmo assim? (s/N)", default="N").lower()
            if confirm in ("s", "sim", "y", "yes"):
                return value
        else:
            return value


def collect_products():
    produtos = []

    while True:
        qty_str = ask("Quantos produtos quer cadastrar?", default="1")
        try:
            qty = int(qty_str)
            if qty >= 1:
                break
            print("  Cadastre ao menos 1 produto.")
        except (ValueError, TypeError):
            print("  Valor invalido. Digite um numero inteiro maior que 0.")

    for i in range(1, qty + 1):
        print()
        print(f"  --- Produto #{i} ---")
        nome = ask(f"Nome do produto #{i}")
        while not nome:
            print("  Nome e obrigatorio.")
            nome = ask(f"Nome do produto #{i}")

        url = ask_url(f"URL/link do produto #{i}")
        descricao = ask_multiline(f"Descricao/diferencial do produto #{i}")
        preco = ask(f"Preco do produto #{i} (ex: R$ 497,00)")
        bonus = ask(f"Bonus do produto #{i} (opcional, Enter para pular)", default="")

        produtos.append(make_product(
            nome=nome,
            url=url,
            descricao=descricao,
            preco=preco,
            bonus=bonus,
        ))
        print(f"  [OK] Produto '{nome}' cadastrado.")

    return produtos


def preview_products(produtos):
    print()
    print("  Preview da base de conhecimento:")
    print()
    for i, p in enumerate(produtos, 1):
        print(f"  [{i}] {p['nome']}")
        if p.get("preco"):
            print(f"      Preco: {p['preco']}")
        print(f"      Link: {p['url']}")
        if p.get("bonus"):
            print(f"      Bonus: {p['bonus']}")
        desc = p.get("descricao", "")
        if desc:
            desc_preview = desc[:80].replace("\n", " ")
            print(f"      Descricao: {desc_preview}{'...' if len(desc) > 80 else ''}")
        print()


def save_kb(produtos):
    INSTAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    # valida antes de salvar
    validate_products(produtos)
    IG_KB_PATH.write_text(
        json.dumps(produtos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  [OK] ig_kb.json salvo em {INSTAGRAM_DIR} ({len(produtos)} produto(s))")


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
