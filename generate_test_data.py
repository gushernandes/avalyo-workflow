#!/usr/bin/env python3
"""
generate_test_data.py — Gera ~1000 ex-usuarios da Avalyo (mock do BigQuery)

Schema por usuario:
  id, nome_restaurante, tipo_restaurante, plano_anterior, data_cadastro,
  data_ultimo_uso, data_churn, ultima_feature_usada, motivo_saida (nullable),
  segmento, stage

Uso:
  python generate_test_data.py --output users.json --n 1000
"""
import argparse
import json
import random
from datetime import datetime, timedelta

PREFIXOS = [
    "Cantina", "Pizzaria", "Bar", "Restaurante", "Bistrô", "Lanchonete",
    "Churrascaria", "Hamburgueria", "Cafeteria", "Trattoria", "Tasca",
    "Boteco", "Empório", "Comedoria", "Casa de",
]
NOMES = [
    "da Nonna", "do Zé", "Bella Vista", "Sabor & Arte", "do Centro", "Maré Alta",
    "Vila Madá", "do Porto", "Recanto", "Estação", "do Chef", "Mineiro",
    "Sabor Caseiro", "Esquina", "Primo", "da Praça", "Aurora", "Bom Prato",
    "do Largo", "Quintal", "Raízes", "do Mercado", "Terraço", "Maracujá",
]
TIPOS = [
    "pizzaria", "hamburgueria", "japonês", "bar", "cafeteria", "churrascaria",
    "italiano", "brasileiro", "rede", "franquia", "padaria", "açaí",
]
PLANOS = ["free", "pro", "enterprise"]
FEATURES = [
    "cardápio digital", "gestão de pedidos", "relatórios de vendas",
    "controle de estoque", "integração iFood", "reservas online",
    "programa de fidelidade", "comanda eletrônica", "delivery próprio",
]
MOTIVOS = [
    "preço alto", "faltou tempo para configurar", "não vi resultado rápido",
    "mudei de sistema", "fechei a operação temporariamente", None, None, None,
]


def iso(d):
    return d.strftime("%Y-%m-%d")


def gen_user(i, today):
    cadastro = today - timedelta(days=random.randint(400, 1200))
    churn = cadastro + timedelta(days=random.randint(60, 700))
    if churn > today:
        churn = today - timedelta(days=random.randint(5, 300))
    ultimo_uso = churn - timedelta(days=random.randint(1, 30))
    plano = random.choices(PLANOS, weights=[0.5, 0.35, 0.15])[0]

    dias_churn = (today - churn).days
    # uso "frequente" antes do churn (proxy: gap pequeno entre ultimo_uso e churn)
    uso_frequente = (churn - ultimo_uso).days <= 7
    if plano in ("pro", "enterprise") and uso_frequente:
        segmento = "alta_propensao"
    elif dias_churn < 90:
        segmento = "churn_recente"
    else:
        segmento = "churn_antigo"

    return {
        "id": f"u{i:05d}",
        "nome_restaurante": f"{random.choice(PREFIXOS)} {random.choice(NOMES)}",
        "tipo_restaurante": random.choice(TIPOS),
        "plano_anterior": plano,
        "data_cadastro": iso(cadastro),
        "data_ultimo_uso": iso(ultimo_uso),
        "data_churn": iso(churn),
        "ultima_feature_usada": random.choice(FEATURES),
        "motivo_saida": random.choice(MOTIVOS),
        "segmento": segmento,
        "stage": 1,  # posicao inicial na regua; a engine gera para todas as etapas
    }


def generate(n=1000, seed=42):
    random.seed(seed)
    today = datetime(2026, 6, 6)
    return [gen_user(i, today) for i in range(1, n + 1)]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="users.json")
    ap.add_argument("--n", type=int, default=1000)
    args = ap.parse_args()
    users = generate(args.n)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    print(f"Gerados {len(users)} usuarios em {args.output}")
