#!/usr/bin/env python3
"""
run_workflow.py — Workflow de automação ponta-a-ponta da régua de CRM (Avalyo)

Orquestra: lê usuários → define posição na régua → seleciona touchpoint →
gera mensagem personalizada → despacha via mock → mantém estado idempotente.

Uso:
  python run_workflow.py --input /home/user/users.json --dispatch-mock /home/user/sent.json

Stdout JSON:
  {"usuarios_processados": N, "touchpoints_disparados": T, "usuarios_saida": S, "erros": E}
"""
import argparse, json, os, sys
from datetime import datetime, date

# ── Régua de CRM ────────────────────────────────────────────────────────────
# 5 touchpoints sequenciais com timing (dias entre contatos)
REGUA = [
    {"stage": "reconhecimento", "canal": "email",     "dias_offset": 0},
    {"stage": "interesse",      "canal": "email",     "dias_offset": 7},
    {"stage": "consideracao",   "canal": "whatsapp",  "dias_offset": 14},
    {"stage": "decisao",        "canal": "whatsapp",  "dias_offset": 21},
    {"stage": "reativacao",     "canal": "email",     "dias_offset": 30},
]

NOVIDADES = {
    "cardápio digital":       "o novo cardápio digital com QR code e fotos que aumenta o ticket médio",
    "gestão de pedidos":      "a gestão de pedidos que unifica salão, delivery e balcão numa tela só",
    "relatórios de vendas":   "os relatórios de vendas em tempo real com previsão de demanda",
    "controle de estoque":    "o controle de estoque que avisa antes de faltar insumo",
    "integração iFood":       "a integração iFood que sincroniza cardápio e estoque automaticamente",
    "reservas online":        "as reservas online com confirmação por WhatsApp",
    "programa de fidelidade": "o programa de fidelidade que já trouxe clientes de volta",
    "comanda eletrônica":     "a comanda eletrônica que reduziu erros de pedido em 40%",
    "delivery próprio":       "o delivery próprio sem comissão de marketplace",
}
NOVIDADE_PADRAO = "as novidades da plataforma dos últimos meses"


def novidade(feature):
    return NOVIDADES.get(feature, NOVIDADE_PADRAO)


def gerar_mensagem(user, stage):
    nome  = user.get("nome_restaurante", "")
    tipo  = user.get("tipo_restaurante", "")
    plano = user.get("plano_anterior", "")
    feat  = user.get("ultima_feature_usada", "")
    nov   = novidade(feat)
    plano_label = {"free": "gratuito", "pro": "Pro", "enterprise": "Enterprise"}.get(plano, plano)

    if stage == "reconhecimento":
        return (f"Oi, {nome}! A Avalyo que você usava para seu {tipo} mudou bastante. "
                f"Lembra do {feat}? Evoluímos muito essa parte. Posso mostrar em 2 min?")
    if stage == "interesse":
        return (f"{nome}, separei uma novidade para seu {tipo}: {nov}. "
                f"Quando você estava no plano {plano_label} isso ainda não existia. Quer ver?")
    if stage == "consideracao":
        return (f"{nome}, {tipo}s que voltaram para a Avalyo estão usando {nov} "
                f"e relatando mais controle. Você já conhecia o {feat} — curva de "
                f"aprendizado quase zero. Topa uma demonstração rápida?")
    if stage == "decisao":
        return (f"{nome}, preparei uma condição de retorno para ex-clientes do plano {plano_label}. "
                f"Você reativa seu {tipo} com {nov} e a gente migra seus dados. "
                f"Posso reservar um horário essa semana?")
    # reativacao
    return (f"Que bom te ter de volta, {nome}! Sua conta do {tipo} está ativa com {nov} "
            f"e o {feat} continua lá. Qualquer dúvida, é só chamar.")


# ── Critérios de saída ───────────────────────────────────────────────────────
def criterio_saida(user, user_state):
    """Retorna True se o usuário deve sair do funil."""
    if user_state.get("reativado"):
        return True
    if user.get("motivo_saida") and user_state.get("tentativas", 0) >= 5:
        return True
    if user_state.get("descadastrado"):
        return True
    return False


# ── Determina próximo touchpoint ─────────────────────────────────────────────
def proximo_touchpoint(user_state, today_str):
    """
    Retorna o índice do próximo touchpoint a enviar, ou None se esgotado/saída.
    Respeita timing entre contatos.
    """
    enviados = user_state.get("enviados", [])   # lista de {stage, data}
    n_enviados = len(enviados)

    if n_enviados >= len(REGUA):
        return None  # todos enviados

    # Calcula data do último envio
    if n_enviados == 0:
        return 0  # nunca contatado → começa agora

    ultimo = enviados[-1]
    ultimo_data = date.fromisoformat(ultimo["data"])
    hoje = date.fromisoformat(today_str)
    dias_desde_ultimo = (hoje - ultimo_data).days
    prox = REGUA[n_enviados]
    # timing mínimo entre touchpoints = diferença de offsets
    if n_enviados == 0:
        min_dias = 0
    else:
        min_dias = prox["dias_offset"] - REGUA[n_enviados - 1]["dias_offset"]

    if dias_desde_ultimo >= min_dias:
        return n_enviados
    return None   # cedo demais — mantém posição


# ── Carrega usuários ─────────────────────────────────────────────────────────
def load_users(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    sys.stderr.write(f"[info] {path} não encontrado; gerando dados de teste.\n")
    from generate_test_data import generate
    return generate(1000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",         default="/home/user/users.json")
    ap.add_argument("--dispatch-mock", default="/home/user/sent.json")
    ap.add_argument("--state-file",    default="/home/user/state.json")
    ap.add_argument("--date",          default=str(date.today()))
    args = ap.parse_args()

    users = load_users(args.input)

    # Carrega estado persistente (idempotência)
    if os.path.exists(args.state_file):
        with open(args.state_file, encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {}

    # Carrega envios existentes (acumula — não duplica)
    if os.path.exists(args.dispatch_mock):
        with open(args.dispatch_mock, encoding="utf-8") as f:
            try:
                sent = json.load(f)
            except json.JSONDecodeError:
                sent = []
    else:
        sent = []

    sent_keys = {(s["id"], s["stage"]) for s in sent}   # guard idempotência

    usuarios_processados = 0
    touchpoints_disparados = 0
    usuarios_saida = 0
    erros = 0

    for user in users:
        uid = user.get("id")
        try:
            user_state = state.get(uid, {"enviados": [], "tentativas": 0})

            # Critério de saída
            if criterio_saida(user, user_state):
                usuarios_saida += 1
                usuarios_processados += 1
                continue

            idx = proximo_touchpoint(user_state, args.date)

            if idx is None:
                # Todos os touchpoints enviados → saída por esgotamento
                if len(user_state.get("enviados", [])) >= len(REGUA):
                    usuarios_saida += 1
                usuarios_processados += 1
                continue

            tp = REGUA[idx]
            stage = tp["stage"]

            # Idempotência: já enviado nessa combinação?
            if (uid, stage) not in sent_keys:
                msg = gerar_mensagem(user, stage)
                despacho = {
                    "id":      uid,
                    "stage":   stage,
                    "canal":   tp["canal"],
                    "data":    args.date,
                    "mensagem": msg,
                }
                sent.append(despacho)
                sent_keys.add((uid, stage))

                # Atualiza estado
                user_state.setdefault("enviados", []).append(
                    {"stage": stage, "data": args.date}
                )
                user_state["tentativas"] = user_state.get("tentativas", 0) + 1

                # Simula reativação: 5% dos usuários de alta propensão reativam no estágio decisão
                if stage == "decisao" and user.get("segmento") == "alta_propensao":
                    import random
                    if random.Random(uid).random() < 0.05:
                        user_state["reativado"] = True

                touchpoints_disparados += 1

            state[uid] = user_state
            usuarios_processados += 1

        except Exception as e:
            sys.stderr.write(f"[erro] usuario {uid}: {e}\n")
            erros += 1
            usuarios_processados += 1

    # Persiste estado e envios
    try:
        with open(args.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except OSError as e:
        sys.stderr.write(f"[warn] não salvou state: {e}\n")

    try:
        with open(args.dispatch_mock, "w", encoding="utf-8") as f:
            json.dump(sent, f, ensure_ascii=False, indent=2)
    except OSError as e:
        sys.stderr.write(f"[warn] não salvou sent: {e}\n")

    print(json.dumps({
        "usuarios_processados":  usuarios_processados,
        "touchpoints_disparados": touchpoints_disparados,
        "usuarios_saida":        usuarios_saida,
        "erros":                 erros,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
