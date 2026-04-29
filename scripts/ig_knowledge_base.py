"""
ig_knowledge_base.py — Base de conhecimento de produtos do aluno.
Gerado automaticamente pelo setup_dm_kb.py. Edite com cuidado.
"""

# Lista de produtos cadastrados pelo aluno
PRODUCTS = [
    # Exemplo (gerado pelo setup):
    # {
    #     "name": "Meu Produto",
    #     "url": "https://exemplo.com/produto",
    #     "description": "Descricao do produto e seus diferenciais.",
    #     "price": "R$ 297",
    #     "bonus": "Bonus opcional",
    # },
]


def get_kb_context():
    """Retorna a base de conhecimento formatada para o prompt do agente."""
    if not PRODUCTS:
        return "Nenhum produto cadastrado ainda."
    lines = ["PRODUTOS DISPONÍVEIS:\n"]
    for i, p in enumerate(PRODUCTS, 1):
        lines.append(f"{i}. {p['name']}")
        lines.append(f"   Link: {p['url']}")
        lines.append(f"   {p['description']}")
        lines.append(f"   Preco: {p['price']}")
        if p.get("bonus"):
            lines.append(f"   Bonus: {p['bonus']}")
        lines.append("")
    return "\n".join(lines)
