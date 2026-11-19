# Devoluções e estornos

> **Status:** implementado na v0.13.0 — pela tela (**Vendas → Devolver / estornar itens**),
> pela API (`POST /v1/devolucoes`) e pelo serviço `ServicoDevolucao`.
> O aviso de que o comprovante **não é documento fiscal** continua valendo.

## Por que devolução não é cancelamento

São operações diferentes, e o programa trata como diferentes:

| | Cancelamento (`ServicoPDV.cancelar_venda`) | Devolução (`ServicoDevolucao`) |
|---|---|---|
| Quando | a venda inteira não valeu (erro de emissão) | parte voltou, ou voltou depois |
| Escopo | todos os itens, sempre | os itens e quantidades que voltaram |
| Motivo | texto livre | **tipo** (arrependimento, defeito, garantia, erro) |
| Prazo | não se aplica | conta da data da venda, por tipo |
| Histórico | venda vira `CANCELADA` | venda **continua** `CONCLUIDA`; a devolução é documento novo |

O cancelamento continua existindo e exige autorização. A devolução **também**:
quem devolve não aprova a própria devolução.

## Tipos e prazos

| Tipo | Prazo padrão | Parâmetro | Origem do número |
|---|---|---|---|
| Arrependimento | 7 dias | `devolucao.prazo_arrependimento_dias` | CDC art. 49 (compra fora do estabelecimento) |
| Defeito / vício aparente | 90 dias | `devolucao.prazo_defeito_dias` | CDC art. 26 |
| Garantia | `garantia_dias` do produto | cadastro do produto | garantia contratual da loja |
| Erro de operação | sem prazo | — | corrigir cobrança errada é sempre possível |

Regras que o código aplica:

- a garantia do produto **só aumenta** o prazo; nunca reduz o legal;
- **fora do prazo** a devolução continua possível, mas exige **autorizador** com a
  permissão `VENDA_DEVOLVER`, e o evento registra `fora_do_prazo = 1`;
- o prazo é contado em dias de **data de negócio** (o fuso da loja), nunca em UTC.

## Destinos do valor

| Destino | O que acontece | Exige |
|---|---|---|
| **Dinheiro** | movimento `ESTORNO_DINHEIRO` no turno aberto | caixa aberto **e** autorizador (dinheiro saindo da gaveta) |
| **Crédito no crediário** | abate as parcelas em aberto do cliente, das mais antigas para as novas, como recebimento na forma `VALE` | venda com cliente identificado, caixa aberto e saldo em aberto suficiente |
| **Troca** | nada se move no caixa; o valor fica na venda nova | nada além da permissão |

O crédito **não** cria título negativo nem dívida do cliente: ele reduz o saldo em
aberto. Se o valor devolvido passar do saldo em aberto, o serviço recusa e pede
dinheiro ou troca — melhor recusar do que inventar um "crédito a favor" que ninguém
controla. (Crédito a favor é ponto de construção, ver abaixo.)

## O que a devolução grava

1. `devolucoes` + `devolucao_itens` — documento e itens, com valor unitário já
   com desconto do item rateado (é o que o cliente pagou, não o preço de tabela);
2. **movimento de estoque** (`ESTORNO`) por item, quando "itens voltam ao estoque"
   está marcado;
3. **movimento de caixa** (`ESTORNO_DINHEIRO`) quando o destino é dinheiro;
4. **recebimento** na forma `VALE` no crediário, quando o destino é crédito;
5. **evento de auditoria** `DEVOLUCAO_REGISTRADA` com tipo, destino, itens, valores,
   dias desde a venda, autorizador e correlação com a venda.

As tabelas de devolução têm trigger que **recusa UPDATE e DELETE**: corrigir é
registrar outra devolução (ou usar o cancelamento), nunca reescrever.

## O que a tela mostra

- tabela com **vendido**, **já devolvido** e **a devolver** por item — a coluna
  editável é só "a devolver";
- o prazo do tipo escolhido em texto: "faltam 3 dia(s) dos 7 do tipo" ou
  "fora do prazo: exige autorização";
- resumo depois de gravar: valor, o que foi para o caixa, o que abateu no crediário,
  se o estoque voltou.

## Pelo teclado / API

```bash
python -m bussola_pdv.cli api --banco dados/bussola.db --token "SEU_TOKEN"

curl -X POST http://127.0.0.1:8765/v1/devolucoes \
  -H "Authorization: Bearer SEU_TOKEN" -H "Content-Type: application/json" \
  -d '{
        "venda_id": "…",
        "tipo": "DEFEITO",
        "destino": "CREDITO_CREDIARIO",
        "motivo": "Produto com defeito",
        "caixa_id": "…",
        "itens": [{"sequencia": 1, "quantidade": "1"}],
        "operador": {"login": "bruno", "senha": "…"},
        "autorizador": {"login": "ana", "senha": "…"}
      }'
```

### Lendo o que ficou gravado

`GET /v1/devolucoes/{id}` devolve o documento com os itens (`venda_item_sequencia`,
`quantidade_milesimos`, `valor_unitario_centavos`, `total_centavos`) direto das tabelas —
é a fonte da 2ª via e da conferência, não o que a tela calculou. O mesmo caminho existe no
programa: `ServicoDevolucao.itens(devolucao_id)`.

## Pontos de construção (o que ainda não existe)

| Falta | Por quê | Caminho |
|---|---|---|
| **Crédito a favor do cliente** | hoje o crédito só abate parcela em aberto; sobra vira recusa | tabela `creditos_cliente` + uso automático na venda |
| **Devolução sem nota/cupom** | exige venda localizada; sem cupom, o operador precisa do código | busca por item/data com autorização |
| **Recolher item com defeito para o fornecedor** | não há controle de item avariado | status de estoque `AVARIADO` + relatório |
| **Estorno de PIX/cartão na maquininha** | o programa não fala com a rede da adquirente | integração com a API da adquirente (projeto separado) |
| **Relatório próprio de devoluções** | hoje aparecem na auditoria e no detalhe da venda | `relatorio_devolucoes` na exportação (Excel/PDF) |

Nenhum desses trava o balcão: o bazar devolve, registra o motivo e o prazo, e o
dinheiro sai certo do caixa ou do crediário.
