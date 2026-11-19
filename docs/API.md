# API HTTP (local e da rede da loja)

> **Status:** v0.14.0. Completa para operar o dia: vender, abrir/fechar turno,
> receber título (com encargo), lançar entrada, devolver e cancelar.
> **Escuta em `127.0.0.1` por padrão** e exige token em toda rota. Para atender
> terminais na rede, `--tls` (obrigatório fora do loopback) — `docs/REDE.md`.
> Não é API de internet: é a porta para integrações locais e para o servidor
> central do multi-caixa.

## Por que existe

O programa é uma tela que fala com serviços de aplicação. A API **não tem regra
própria**: cada rota chama o mesmo serviço que a tela chama (`ServicoDevolucao`,
`ServicoPDV`, `ServicoExportacao`). Isso é o que garante que o relatório, a tela e a
integração nunca discordem sobre um número.

## Subir o servidor

```bash
# Windows (PowerShell), base em D:\pdv
set BUSSOLA_API_TOKEN=cole-aqui-um-token-longo-e-aleatorio
"D:\Program Files\Python314\python.exe" -m bussola_pdv.cli api --banco D:\pdv\bussola.db

# Linux/macOS
BUSSOLA_API_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')" \
  python3 -m bussola_pdv.cli api --banco dados/bussola.db --porta 8765
```

Saída: `API no ar em http://127.0.0.1:8765/v1`.

| Parâmetro | Padrão | Observação |
|---|---|---|
| `--banco` | `dados/bussola.db` | a base do PDV |
| `--token` | `BUSSOLA_API_TOKEN` | mínimo de 16 caracteres, obrigatório |
| `--host` | `127.0.0.1` | `0.0.0.0` **exige** `--tls` (senão o comando recusa) |
| `--porta` | `8765` | porta efêmera com `0` (útil em teste) |
| `--tls` | desligado | gera/reaproveita certificado autoassinado em `<dados>/tls` |
| `--tls-pasta` | `<dados>/tls` | onde ficam `servidor.crt` e `servidor.key` |
| `--terminal` | `CAIXA-01` | identificador deste caixa |
| `--log-acesso` | `<dados>/logs/api-AAAA-MM-DD.jsonl` | uma linha JSON por requisição |

### TLS na rede da loja

O certificado é **autoassinado e gerado pelo programa** (RSA 2048 + X.509 v3, em
biblioteca padrão — não precisa instalar OpenSSL). Na subida, o comando imprime:

```
TLS: certificado autoassinado em D:\pdv\tls\servidor.crt
     impressão digital SHA-256: 3A:91:...:F0
```

Conferir essa impressão no terminal (por telefone ou olhando a tela do servidor) é o
que substitui a autoridade certificadora. Vale para a rede local; **não** serve para
expor a API na internet.

### Quem fez: o cabeçalho do terminal

`X-Bussola-Terminal: BALCAO-2` (opcional, padrão `--terminal`). O valor é gravado em
`vendas.terminal_id` e `turnos.terminal_id` e aparece no log de acesso. Sem ele, dois
caixas na mesma base são indistinguíveis no histórico.

## Autenticação em duas camadas

1. **Token do aplicativo** — cabeçalho `Authorization: Bearer <token>` em **todas**
   as rotas. Identifica o programa, não a pessoa.
2. **Credenciais da pessoa** — em toda rota que **grava**, o corpo precisa de
   `operador: {login, senha}` e, quando a regra pede segundo responsável,
   `autorizador: {login, senha}`. É a mesma autorização nominal da tela: quem autoriza
   fica na auditoria.

Falha na camada 1 → `401`. Falha na camada 2 → `401` também, mas com o motivo
(`operador.login e operador.senha`).

## Rotas

### Leitura (token)

| Método | Rota | Devolve |
|---|---|---|
| GET | `/v1/saude` | versão da API, versão do esquema, data de negócio |
| GET | `/v1/produtos?busca=&limite=` | produtos com preço, custo, garantia e **saldo** |
| GET | `/v1/estoque?busca=` | o mesmo relatório de estoque da exportação (colunas e linhas) |
| GET | `/v1/vendas?de=&ate=&limite=` | vendas do período |
| GET | `/v1/vendas/{id}` | venda com itens, pagamentos, **total devolvido** e **itens devolvíveis** |
| GET | `/v1/crediario?cliente_id=&incluir_pagos=` | títulos e saldos |
| GET | `/v1/devolucoes?venda_id=&limite=` | devoluções registradas |
| GET | `/v1/devolucoes/{id}` | uma devolução com os itens gravados (404 se não existe) |
| GET | `/v1/turnos` | turnos abertos (caixa, terminal, operador, fundo) |
| GET | `/v1/relatorios/{estoque,clientes,crediario,entradas,auditoria}` | relatório pronto, com avisos |

### Escrita (token + login/senha)

| Método | Rota | Corpo |
|---|---|---|
| POST | `/v1/vendas` | `caixa_id`, `itens[{codigo,quantidade,desconto_centavos?}]`, `pagamentos[{forma,valor_centavos}]`, `operador`, `cliente_id?`, `autorizador?`, `parcelas_crediario?`, `chave_idempotencia?` |
| POST | `/v1/vendas/{id}/cancelar` | `motivo`, `operador`, `autorizador`, `devolver_estoque?` |
| POST | `/v1/turnos` | `caixa`, `fundo_centavos`, `operador` |
| POST | `/v1/turnos/{id}/fechar` | `contagens[{denominacao,quantidade}]`, `operador`, `motivo_diferenca?` |
| POST | `/v1/crediario/{titulo_id}/receber` | `valor_centavos`, `forma`, `caixa_id`, `operador`, `cobrar_encargos?`, `motivo_dispensa?`, `autorizador?` |
| POST | `/v1/entradas` | `fornecedor`, `documento`, `itens[{codigo,quantidade,custo_unitario_centavos}]`, `frete_centavos?`, `operador` |
| POST | `/v1/devolucoes` | `venda_id`, `tipo`, `destino`, `motivo`, `itens[{sequencia,quantidade}]`, `operador`, `autorizador?`, `caixa_id?`, `devolver_estoque?` |

`A_PRAZO` em `pagamentos` gera o crediário (`parcelas_crediario`). Formas eletrônicas
nascem **pendentes**, como na tela — a API não confirma o que a adquirente não mandou.
`chave_idempotencia` é o que evita venda duplicada quando a rede oscila e o terminal
repete o `POST`: a segunda chamada devolve `ja_existia: true` em vez de vender duas vezes.

`tipo`: `ARREPENDIMENTO`, `DEFEITO`, `GARANTIA`, `ERRO_OPERACIONAL`.
`destino`: `DINHEIRO`, `CREDITO_CREDIARIO`, `TROCA` (regras em `docs/DEVOLUCOES.md`).

## Exemplos

```bash
TOKEN="seu-token"
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/v1/saude

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8765/v1/produtos?busca=cafe"

curl -s -X POST http://127.0.0.1:8765/v1/devolucoes \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "venda_id": "ID-DA-VENDA",
    "tipo": "ARREPENDIMENTO",
    "destino": "DINHEIRO",
    "motivo": "Cliente desistiu",
    "caixa_id": "ID-DO-CAIXA",
    "itens": [{"sequencia": 1, "quantidade": "1"}],
    "operador":    {"login": "bruno", "senha": "…"},
    "autorizador": {"login": "ana",   "senha": "…"}
  }'

# venda pelo terminal do balcão
curl -s -X POST https://127.0.0.1:8765/v1/vendas \
  -H "Authorization: Bearer $TOKEN" -H "X-Bussola-Terminal: BALCAO-2" \
  -H "Content-Type: application/json" \
  --cacert dados/tls/servidor.crt \
  -d '{
    "caixa_id": "ID-DO-CAIXA",
    "itens": [{"codigo": "A001", "quantidade": "1"}],
    "pagamentos": [{"forma": "DINHEIRO", "valor_centavos": 1590}],
    "operador": {"login": "carla", "senha": "…"}
  }'
```

## Códigos de erro

| Código | Quando | Corpo |
|---|---|---|
| 200 | ok | JSON da rota |
| 400 | corpo/tipo/destino inválido | `{"erro": ..., "detalhe": {"tipos": [...], "destinos": [...]}}` |
| 401 | token ausente/errado ou credencial inválida | `{"erro": ...}` |
| 404 | rota ou registro inexistente | `{"erro": ...}` |
| 409 | conflito de regra (venda já cancelada, fora do prazo sem autorizador) | `{"erro": ...}` |
| 422 | validação de negócio (quantidade acima do vendido) | `{"erro": ...}` |
| 500 | falha inesperada | `{"erro": "Erro interno na API.", "tipo": "..."}` |

Nunca sai *stack trace* na resposta. O detalhe completo fica na auditoria e no log
local.

## Limites conhecidos (v0.14.0)

- **a tela ainda não é cliente da API**: o programa do balcão abre a base direto.
  As rotas existem e estão testadas; transformar a tela em terminal remoto é o
  incremento seguinte (`docs/REDE.md`, seção "o que falta");
- **sem paginação por cursor**: `limite` corta, e o resto não vem;
- **sem rate limit por terminal**: um único token ou um por máquina, decisão da loja;
- **sem revogação de token em quente**: trocar exige reiniciar o servidor.

## Como testar

- `tests/test_api.py` — servidor em porta efêmera, HTTP de verdade: token ausente,
  token errado, produto com saldo, venda com itens devolvíveis, devolução com
  credencial, tipo inválido (com a lista dos aceitos), cancelamento sem autorizador
  e devolução consultada por id.
- `tests/test_rede_multi_caixa.py` — **HTTPS** com o certificado gerado pelo
  programa: handshake, recusa sem confiar no certificado, terminal por cabeçalho
  gravado na venda, log de acesso em JSONL, as rotas de escrita novas e **dois
  terminais vendendo ao mesmo tempo** com o último item disputado.
- `tests/test_certificado.py` — o certificado em si: DER canônico, série positiva,
  RDN em SET, SAN, assinatura RSA verificada com `pow(s, e, n)`, digital estável e
  `obter_ou_criar` idempotente.
