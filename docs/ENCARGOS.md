# Juros e encargos de atraso (cobrados desde a v0.14.0)

> **Status:** a calculadora (`dominio/encargos.py`) **é usada** no recebimento do
> crediário desde a v0.14.0, mas a cobrança nasce **desligada** de fábrica
> (`encargos.cobrar = 0`). Quem liga é o admin, em *Administração → Parâmetros*.

## Por que a conta mora no domínio

Cobrar juros "de cabeça" é o que a caderneta fazia — e é o tipo de conta que gera
discussão no balcão. A regra fica numa função pura, testada, com memória de cálculo
que o operador pode mostrar ao cliente.

## Fórmula aplicada

```
dias        = referência − vencimento            (nunca negativo)
se dias ≤ carência → encargos = 0
multa       = principal × multa                    (uma vez)
juros       = principal × juros_mês × (dias − carência) ÷ (30 × 100%)
total       = multa + juros
```

- juros **simples**, proporcionais aos dias, com mês comercial de 30 dias;
- uma única divisão no fim, arredondamento **meio para cima** — nada de `float`;
- tudo em centavos e pontos-base (`Percentual`), como o resto do dinheiro do programa;
- o `principal` é o **saldo em aberto** do título na data do recebimento (parcial
  recebido antes sai da base do cálculo).

## Parâmetros

| Chave | Padrão | Significado |
|---|---|---|
| `encargos.cobrar` | `0` (desligado) | liga a cobrança no recebimento |
| `encargos.multa_bp` | `200` | 2,00% de multa, uma vez |
| `encargos.juros_mes_bp` | `100` | 1,00% ao mês, proporcional aos dias |
| `encargos.carencia_dias` | `0` | dias de tolerância antes de qualquer encargo |

## Exemplo conferível na mão

Título de **R$ 100,00**, vencimento 01/10, referência 31/10 → 30 dias de atraso:

| Parcela | Conta | Valor |
|---|---|---|
| Multa | 100,00 × 2% | R$ 2,00 |
| Juros | 100,00 × 1% × 30 ÷ 30 | R$ 1,00 |
| **Total** | | **R$ 3,00** — recebe-se R$ 103,00 |

`EncargosDevidos.memoria` devolve essas linhas em texto; a tela de recebimento mostra
a frase antes de confirmar.

## Como o encargo é cobrado e registrado (ADR-033)

O encargo **não** entra no título. O título continua com o valor original e quita
pelo principal; o encargo é receita identificada do dia:

| Onde | O que grava |
|---|---|
| `recebimentos` | `multa_centavos`, `juros_centavos`, `encargo_centavos`, `dias_atraso` |
| `movimentos_caixa` | tipo `RECEBIMENTO_ENCARGOS` (só quando a forma é dinheiro) |
| auditoria | `multa_centavos`, `juros_centavos`, `dias_atraso`, `encargos_dispensados_centavos`, `autorizador_id`, `motivo_dispensa` |
| fechamento | linha "Encargos de atraso (multa + juros)", somada no esperado da gaveta |

Assim o fechamento responde duas perguntas diferentes: *quanto entrou de mercadoria*
(`recebimentos_centavos`) e *quanto entrou de encargo* (`encargos_centavos`).
Cartão/PIX não passam pela gaveta — o encargo é registrado no recebimento e não gera
movimento de caixa, como o principal.

## Perdoar o encargo é operação sensível

Com a cobrança ligada, desmarcar "cobrar multa e juros" na tela de recebimento exige:

1. **senha de um autorizador** com a permissão `TITULO_ENCARGO_DISPENSAR`
   (de fábrica: gerente e admin — o atendente cobra, não perdoa);
2. **motivo escrito**.

O recebimento fica com `encargos_dispensados = 1` e a auditoria guarda quanto foi
perdoado e quem autorizou. Perdoar sem deixar rastro é o que a caderneta fazia.

## Limites legais (continuam valendo)

| Regra | Referência |
|---|---|
| Multa de mora ≤ 2% sobre o valor da prestação | CDC art. 52 §1º |
| Juros de mora ≤ 1% ao mês | Decreto 22.626/33 (Lei de Usura) |
| Informação prévia ao consumidor | CDC art. 52 |

O programa **não** impede percentual acima disso (o dono pode ter contrato
específico), mas os padrões de fábrica ficam no limite legal. Baixar ou subir é
decisão do negócio, registrada na auditoria de parâmetros.

## O que ainda não existe

| Falta | Por quê |
|---|---|
| Correção monetária por índice (IGP-M/IPCA) | exige série de índices e decisão jurídica |
| Renegociação/parcelamento de dívida vencida | modelo novo (título derivado), não é encargo |
| Aviso ao cliente antes de vencer | depende de canal (WhatsApp/e-mail) — fora do escopo offline |
| Não cobrar encargo para cliente com pendência judicial | não há cadastro de exceção |
