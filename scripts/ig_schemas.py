#!/usr/bin/env python3
"""
Schemas e validators centralizados para ig-autoflow.
Fonte única de verdade para todos os save/load de ig_triggers.json e ig_kb.json.
"""

from typing import List


# ---------------------------------------------------------------------------
# Trigger schema
# ---------------------------------------------------------------------------

class Trigger(dict):
    """keyword + textos de reply/dm + url opcional."""


def validate_triggers(data) -> List[Trigger]:
    if not isinstance(data, list):
        raise ValueError("ig_triggers.json deve ser uma lista, nao um objeto")
    for i, t in enumerate(data):
        if not isinstance(t, dict):
            raise ValueError(f"trigger #{i} deve ser um objeto, encontrado: {type(t).__name__}")
        for key in ("keywords", "reply_text", "dm_text"):
            if key not in t:
                raise ValueError(f"trigger #{i} sem campo obrigatorio '{key}'")
        if not isinstance(t["keywords"], list) or not t["keywords"]:
            raise ValueError(f"trigger #{i}: 'keywords' deve ser lista nao-vazia")
    return data


def make_trigger(keywords, reply_text, dm_text, url="") -> Trigger:
    if isinstance(keywords, str):
        keywords = [keywords]
    return {
        "keywords": [k.lower().strip() for k in keywords],
        "reply_text": reply_text,
        "dm_text": dm_text,
        "url": url,
    }


# ---------------------------------------------------------------------------
# Product schema (pt-br padronizado)
# ---------------------------------------------------------------------------

class Product(dict):
    """Produto/servico para base de conhecimento do DM Agent."""


def validate_products(data) -> List[Product]:
    if not isinstance(data, list):
        raise ValueError("ig_kb.json deve ser uma lista, nao um objeto")
    for i, p in enumerate(data):
        if not isinstance(p, dict):
            raise ValueError(f"produto #{i} deve ser um objeto")
        for key in ("nome", "url"):
            if key not in p:
                raise ValueError(f"produto #{i} sem campo obrigatorio '{key}'")
    return data


def make_product(nome, url, descricao="", preco="", bonus="") -> Product:
    return {
        "nome": nome,
        "url": url,
        "descricao": descricao,
        "preco": preco,
        "bonus": bonus,
    }


def products_to_kb_text(products: List[Product]) -> str:
    """Converte lista de produtos para texto de contexto do DM Agent."""
    if not products:
        return "Sem base de conhecimento configurada."
    lines = ["=== BASE DE CONHECIMENTO ===\n"]
    for i, p in enumerate(products, 1):
        lines.append(f"Produto {i}: {p.get('nome', 'N/A')}")
        if p.get("preco"):
            lines.append(f"  Preco: {p['preco']}")
        if p.get("url"):
            lines.append(f"  Link: {p['url']}")
        if p.get("descricao"):
            lines.append(f"  Descricao: {p['descricao']}")
        if p.get("bonus"):
            lines.append(f"  Bonus: {p['bonus']}")
        lines.append("")
    return "\n".join(lines)
