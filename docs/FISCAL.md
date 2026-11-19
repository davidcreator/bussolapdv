# Emissão fiscal: o que seria preciso para homologar

> **Status nesta versão: desligado por decisão (ADR-029).**
> O programa é controle interno (bazar de ONG, no lugar da caderneta) e **não emite
> documento fiscal**. O cupom, os relatórios e o manual dizem isso no rodapé — e vão
> continuar dizendo mesmo depois de uma futura homologação: o comprovante interno não
> vira nota por decreto.
>
> Este documento existe para que a decisão de emitir seja tomada com o custo à vista,
> e para que a implementação entre por uma porta só. O contrato já está no código:
> `src/bussola_pdv/aplicacao/fiscal.py` (`EmissorFiscal`, `DocumentoFiscal`,
> `EmissorFiscalDesativado`, `configuracao_fiscal`).

## 1. Decisão de negócio (antes de qualquer código)

| Pergunta | Por que importa |
|---|---|
| O bazar é **contribuinte** com inscrição estadual ativa? | MEI e Simples têm regras e obrigações diferentes; sem IE não há NFC-e |
| Emitir **NFC-e modelo 65** (cupom) ou **NF-e modelo 55** (venda com transporte)? | modelo muda o XML, o DANFE e o autorizador |
| Quem assina: a ONG ou a loja que cede o espaço? | CNPJ do emitente vai no XML e no certificado |
| Existe contador acompanhando? | homologação sem contador vira retrabalho |
| As vendas do **crediário** e as **devoluções** viram nota? | devolução fiscal tem documento próprio (NF-e de entrada/devolução) |

## 2. Requisitos técnicos

1. **Certificado digital A1** (`.pfx`, arquivo) ou A3 (token) — recomendado A1 para
   instalação em `D:\pdv`, com senha guardada protegida pelo Windows.
2. **CSC** (Código de Segurança do Contribuinte) e **ID do token**, obtidos no portal
   da SEFAZ do estado — usados no QR Code da NFC-e.
3. **Inscrição estadual** ativa e **CNAE** compatível com comércio varejista.
4. **Autorizador da UF** (webservice SOAP da SEFAZ) e **endpoint de contingência**.
5. **Relógio sincronizado** (a SEFAZ rejeita nota com data fora de tolerância) — hoje
   o programa já recusa operar com fuso errado.
6. **Numeração e série** controladas por estabelecimento — o programa já tem série e
   número sequencial de venda; a nota precisa da sua própria sequência.
7. **Armazenamento do XML** por 5 anos (obrigação legal) — o contrato de nuvem
   (`docs/NUVEM.md`) é o caminho natural para a cópia fora da máquina.

## 3. O que muda no programa (estimativa honesta)

| Etapa | Trabalho | Risco |
|---|---|---|
| 1. Assinatura XML (XMLSec + certificado) | biblioteca nova, testes com certificado de teste | médio (dependência Windows) |
| 2. Geração do XML NFC-e (leiaute 4.00) | ~40 campos obrigatórios, tributos por item (NCM, CFOP, CST/CSOSN) | **alto** — exige contador |
| 3. Transmissão e retorno (SOAP, mTLS) | cliente HTTP com certificado, tratamento de rejeição | alto |
| 4. QR Code + DANFE simplificado | impressão térmica já existe; muda o layout do cupom | baixo |
| 5. Contingência (offline) | fila de notas pendentes e reenvio | médio |
| 6. Cancelamento e inutilização de numeração | prazo de 30 min para cancelar na SEFAZ | médio |
| 7. Devolução fiscal | NF-e de devolução ligada à nota original | alto |
| 8. Homologação em ambiente de teste da UF | rodada com o contador, casos de rejeição | médio |
| 9. Produção assistida | primeiras notas com acompanhamento | baixo |

Ordem de grandeza: **4 a 8 semanas** de desenvolvimento e homologação, mais o custo
recorrente do certificado (R$ 150–400/ano) e do contador.

## 4. Pontos de construção já preparados no código

- `EmissorFiscal` (protocolo): `emitir`, `cancelar`, `consultar` — qualquer provedor
  (SEFAZ direto, gateway, contingência) entra sem mexer na venda.
- `DocumentoFiscal`: chave, protocolo, XML, PDF do DANFE, situação e avisos.
- `EmissorFiscalDesativado`: recusa com **motivo e lista de pendências**, em vez de
  devolver documento falso. É o que está ativo hoje.
- `configuracao_fiscal(contexto)`: lê `fiscal.*` e `empresa.*` dos parâmetros.
- `SituacaoFiscal`: `DESATIVADO`, `EM_HOMOLOGACAO`, `AUTORIZADO`, `REJEITADO`,
  `CONTINGENCIA`, `CANCELADO` — o vocabulário que a tela vai usar.

## 5. Parâmetros previstos

| Chave | Uso |
|---|---|
| `fiscal.habilitado` | liga a emissão (hoje ausente = desligado) |
| `fiscal.ambiente` | `HOMOLOGACAO` ou `PRODUCAO` |
| `fiscal.uf` | define o autorizador |
| `fiscal.serie_nfce` | série da NFC-e |
| `fiscal.certificado` | caminho do `.pfx` |
| `fiscal.csc_id`, `fiscal.csc_token` | QR Code |

## 6. O que **não** muda

- O aviso **"não é documento fiscal"** no cupom e nos relatórios continua até que
  exista nota autorizada — e, mesmo depois, o cupom interno continua sendo interno.
- A trilha de auditoria continua registrando venda, devolução e cancelamento; a nota
  fiscal é um **documento adicional**, com sua própria numeração e seu próprio ciclo.
- A operação continua **offline**: contingência é regra fiscal, não desculpa para
  depender de internet no balcão.

## 7. Próximo passo recomendado

Se a decisão for emitir: contratar contador, obter certificado A1 e CSC de
homologação, e implementar as etapas 1–3 com um **gateway de emissão** (menos código
sensível no produto) antes de tentar SEFAZ direto. Sem esses três itens na mão, nenhum
código escrito aqui deixa de ser exercício teórico.
