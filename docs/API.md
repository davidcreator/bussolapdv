# API HTTP local

> **Status:** funciona na v0.13.0, disponível por comando (`bussola api`).
> **Escuta em `127.0.0.1` por padrão** e exige token em toda rota.
> Não é API de internet: é a porta para integrações locais e para o servidor
> central do multi-caixa (`docs/REDE.md`).

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
| `--host` | `127.0.0.1` | `0.0.0.0` só atrás de proxy com TLS |
| `--porta` | `8765` | porta efêmera com `0` (útil em teste) |

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
| GET | `/v1/relatorios/{estoque,clientes,crediario,entradas,auditoria}` | relatório pronto, com avisos |

### Escrita (token + login/senha)

| Método | Rota | Corpo |
|---|---|---|
| POST | `/v1/devolucoes` | `venda_id`, `tipo`, `destino`, `motivo`, `itens[{sequencia,quantidade}]`, `operador`, `autorizador?`, `caixa_id?`, `devolver_estoque?` |
| POST | `/v1/vendas/{id}/cancelar` | `motivo`, `operador`, `autorizador`, `devolver_estoque?` |

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

## Limites conhecidos (v0.13.0)

- **escrita parcial**: venda, turno, recebimento e entrada ainda são só pela tela
  (as rotas entram junto com o modo servidor do `docs/REDE.md`);
- **sem TLS embutido**: em rede, use proxy reverso com certificado;
- **sem paginação por cursor**: `limite` corta, e o resto não vem;
- **sem log de acesso**: deliberado no modo local — em rede, isso é requisito.

## Como testar

`tests/test_api.py` sobe o servidor em porta efêmera e fala HTTP de verdade: token
ausente, token errado, produto com saldo, venda com itens devolvíveis, devolução com
credencial, tipo inválido (com a lista dos aceitos) e cancelamento sem autorizador.
