# Avalyo — Workflow de automação ponta-a-ponta da régua de CRM

Solução para o eval **"Workflow de automação ponta-a-ponta da régua de CRM (orquestração + API)"**.

Orquestra a régua completa de reativação: lê ex-usuários, define posição na régua de CRM, seleciona o touchpoint correto, gera mensagem personalizada e despacha via mock.

## Como rodar

```bash
pip install -r requirements.txt
python run_workflow.py --input /home/user/users.json --dispatch-mock /home/user/sent.json
```

Saída stdout:

```json
{"usuarios_processados": 1000, "touchpoints_disparados": 1000, "usuarios_saida": 0, "erros": 0}
```

## Régua de CRM (5 touchpoints sequenciais)

| # | Stage | Canal | Timing |
|---|-------|-------|--------|
| 1 | reconhecimento | email | dia 0 |
| 2 | interesse | email | dia 7 |
| 3 | consideracao | WhatsApp | dia 14 |
| 4 | decisao | WhatsApp | dia 21 |
| 5 | reativacao | email | dia 30 |

## Idempotência

O workflow mantém `state.json` com o histórico de envios por usuário. Rodar 2x no mesmo dia não gera novos disparos — o run 2 retorna `touchpoints_disparados: 0`.

## Critérios de saída do funil

- **Reativou**: detectado no estágio "decisao" para usuários `alta_propensao` (5% de probabilidade simulada)
- **Descadastrou**: `motivo_saida` presente + 5+ tentativas
- **Esgotou tentativas**: todos os 5 touchpoints enviados

## sent.json

Cada entrada: `{id, stage, canal, data, mensagem}`. Formato válido e auditável.

## BigQuery (produção)

Substitua o argumento `--input` por credenciais GCP:

```bash
python run_workflow.py \
  --project-id seu-projeto \
  --dataset avalyo \
  --table ex_usuarios \
  --dispatch-mock sent.json
```

## Dados de teste

```bash
python generate_test_data.py --output users.json --n 1000
```
