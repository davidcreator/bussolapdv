# Juros e encargos de atraso (base pronta, ainda não cobrados)

> **Status:** a **calculadora** existe e está testada (`dominio/encargos.py`), mas o
> programa **não cobra** juros nem multa de crediário atrasado (pendência P3). Nenhum
> título é alterado por ela hoje.

## Por que a conta mora no domínio

Cobrar juros "de cabeça" é o que a caderneta fazia — e é o tipo de conta que gera
discussão no balcão. A regra fica numa função pura, testada, com memória de cálculo
que o operador pode mostrar ao cliente; o dia em que a loja decidir cobrar, liga-se o
resultado ao título sem espalhar aritmética pela tela.

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
- tudo em centavos e pontos-base (`Percentual`), como o resto do dinheiro do programa.

## Parâmetros (padrões conservadores)

| Chave | Padrão | Significado |
|---|---|---|
| `encargos.multa_bp` | `200` | 2,00% de multa, uma vez |
| `encargos.juros_mes_bp` | `100` | 1,00% ao mês, proporcional aos dias |
| `encargos.carencia_dias` | `0` | dias de tolerância antes de qualquer encargo |

## Exemplo conferível na mão

Título de **R$ 100,00**, vencimento 01/10, referência 31/10 → 30 dias de atraso:

| Parcela | Conta | Valor |
|---|---|---|
| Multa | 100,00 × 2% | R$ 2,00 |
| Juros | 100,00 × 1% × 30 ÷ 30 | R$ 1,00 |
| **Total** | | **R$ 3,00** → R$ 103,00 |

`EncargosDevidos.memoria` devolve essas linhas em texto, prontas para a tela ou para o
recibo.

## O que falta para cobrar (decisão, não código)

| Falta | Quem decide |
|---|---|
| Cobrar ou não cobrar (e a partir de quantos dias) | dono da loja |
| Percentuais de multa e juros | contador / jurídico |
| Limite legal (multa de mora ≤ 2%, juros ≤ 1% ao mês, salvo contrato) | jurídico |
| Como o encargo entra no título (acréscimo em `titulos.encargos_centavos`, que já existe) | produto |
| Renegociação/parcelamento da dívida | produto |
| Aviso ao cliente antes de cobrar | produto |

Quando a decisão vier, o caminho é curto: calcular no recebimento, somar em
`encargos_centavos`, registrar na auditoria com a memória de cálculo e mostrar no
cupom. A conta já está pronta e conferida — o que falta é a política.
