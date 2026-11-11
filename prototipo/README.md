# Protótipo e especificação histórica

Este diretório guarda o **material original** do projeto Bússola: a documentação de especificação
(23 documentos), as 20 pastas de trabalho `.xlsx` do protótipo em planilha, os 5 módulos VBA e os 20
scripts Python que geraram essas planilhas.

> **Não é fonte de verdade do sistema.** Nada aqui é executado pela aplicação em `src/`. Estes
> arquivos ficaram preservados por valor histórico e como referência de regra de negócio.

**Origem:** clone do repositório público <https://github.com/davidcreator/bussolapdv>, commit
`fd4e1e4` ("inicio de projeto"), feito em 11/11/2026, preservado aqui sem alterar o conteúdo — exceto
os três documentos de raiz renomeados com sufixo `_ORIGINAL` para não colidir com os do sistema.

## Estado real destes arquivos

| Item | O que é | Cuidado |
|---|---|---|
| `especificacao/docs/` | 23 documentos de especificação (`.md`) + 23 cópias `.txt` **idênticas** | as cópias `.txt` são duplicatas byte a byte; edite apenas o `.md` |
| `especificacao/excel/` | 20 `.xlsx` com 16 abas cada | são **20 estados intermediários** do mesmo modelo, não versões de um produto; não há arquivo canônico |
| `especificacao/py/` | 20 scripts `build_*.py` que geraram as planilhas | uso único, sem `requirements.txt`, sem testes; um deles grava em caminho absoluto `/home/user/...` |
| `especificacao/py/*.bas` | 5 módulos VBA quase idênticos (694 linhas) | gravam venda **sem transação**: falha no meio deixa dados parciais |
| `especificacao/uploads/` | 3 capturas de tela de terceiros | **não redistribuir** sem verificar licença (pendência registrada no NOTICE) |
| `especificacao/README_ORIGINAL.md`, `CHANGELOG_ORIGINAL.md`, `NOTICE_ORIGINAL.md` | documentos do repositório de origem, preservados como estavam | contêm afirmações desatualizadas (ex.: "o repositório ainda não foi criado", templates de issue inexistentes) |
| `especificacao/PROMPT_MESTRE_PYTHON.md` | o briefing que definiu arquitetura e sequência de implementação | é o contrato seguido por `docs/PLANO_IMPLEMENTACAO.md` |

## Onde está o sistema

- Código: `src/bussola_pdv/`
- Testes: `tests/`
- Documentação vigente: `docs/` (análise, ADRs, plano, capturas)
- Diagnóstico completo deste material: `docs/ANALISE_REPOSITORIO.md`

## Antes de usar qualquer planilha como referência

Leia `docs/ANALISE_REPOSITORIO.md` §4.2. As planilhas **não** devem ser importadas para uma base de
produção sem mapeamento, validação e aprovação explícita — a importação está listada como pendência
(P10 em `docs/DECISOES.md`).
