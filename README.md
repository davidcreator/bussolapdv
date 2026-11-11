# Bússola Sistema PDV Open Source

PDV desktop **offline**, em Python + PySide6 + SQLite, para varejo brasileiro.

> **Estado: pré-alfa funcional (v0.2.0).** O núcleo de domínio, a persistência, os casos de uso de
> venda/caixa/crediário/estoque/fechamento, a trilha de auditoria, a interface inicial e a área
> administrativa com hierarquia de perfis e tema da loja existem e têm testes automatizados. **Não é homologado para operação real**, não emite documento fiscal, não
> suporta múltiplas estações em rede e não substitui contador ou sistema fiscal certificado.
> Leia [docs/PLANO_IMPLEMENTACAO.md](docs/PLANO_IMPLEMENTACAO.md) e [docs/DECISOES.md](docs/DECISOES.md)
> antes de qualquer uso com dados reais.

A implementação em Python e o material de especificação/protótipo que a originou vivem **no mesmo
diretório**, separados por papel: código em `src/` e `tests/`; documentação vigente em `docs/`;
material histórico e planilhas em `prototipo/` (que **não** é executado nem é fonte de verdade).
O diagnóstico do que existia antes está em [docs/ANALISE_REPOSITORIO.md](docs/ANALISE_REPOSITORIO.md)
e o inventário do material antigo em [prototipo/README.md](prototipo/README.md).

![Tela do PDV](docs/capturas/02_pdv_com_itens.png)

![Área administrativa](docs/capturas/11_admin_permissoes.png)

## O que já funciona

- **Venda atômica e idempotente**: venda, itens, pagamentos, saída de estoque, títulos e auditoria
  entram na mesma transação. Falha em qualquer etapa → rollback total (testado com falha injetada).
- **Pagamento dividido em até 3 formas**, com troco limitado a dinheiro; PIX/cartão nascem
  `PENDENTE` e exigem confirmação registrada.
- **Caixa por turno**: um único turno aberto por caixa (garantido por índice no banco), sangria com
  autorização, suprimento, contagem por denominação e fechamento com justificativa de diferença.
- **Crediário**: parcelas com trava de fim de mês, recebimento parcial/total, aging 1–30/31–60/61–90/
  >90, limite e bloqueio por atraso — sem encargos inventados.
- **Estoque** por movimentos assinados, status ruptura/baixo/reposição/OK, rateio de frete com soma
  exata em centavos.
- **Auditoria append-only** com triggers que abortam `UPDATE`/`DELETE` e cadeia SHA-256 verificável.
- **Segurança**: Argon2id, bloqueio por tentativas, autorização por ação exige autenticação de outro
  usuário com permissão.
- **Hierarquia de cinco perfis** (`ADMIN_MASTER > ADMIN > GERENTE > CONTABILIDADE > ATENDENTE`) com
  matriz de permissões editável **apenas pelo Admin Master**, aplicada na hora e auditada.
- **Marca e tema da loja** editáveis no painel (nome, razão social, CNPJ, endereço, rodapé do cupom,
  logo) e paleta de cores com presets claro/escuro — o tema vale para a interface inteira.
- **Área administrativa** com diagnóstico real de dependências, cadastros, parâmetros, cópias de
  segurança verificadas e restauração.
- **Backup consistente** pela API do SQLite, com verificação de integridade e teste de restauração.
- **Demonstração offline** com 16 produtos, 5 clientes, 16 vendas em 3 dias, uma venda cancelada e um
  crediário de 3 parcelas — tudo fictício.

## Hierarquia de perfis

O nível é um número; quem está acima gerencia quem está abaixo, e ninguém edita o próprio acesso.

| Perfil | Nível | Em uma frase |
|---|---|---|
| **Admin Master** | 100 | proprietário da instalação: define o que cada perfil acessa, faz backup e restauração |
| **Admin** | 70 | opera o sistema inteiro (cadastros, parâmetros, usuários abaixo dele), sem mexer na matriz |
| **Gerente** | 40 | autoriza desconto acima do limite, sangria, estoque negativo, cancelamento e fechamento |
| **Contabilidade** | 30 | só leitura: relatórios, fechamentos, títulos, auditoria — não vende, não cancela |
| **Atendente** | 20 | frente de caixa: vende, consulta preço e abre/fecha o próprio turno |

A matriz de permissões tem uma linha por ação (venda, caixa, cadastro, relatório, administração) e uma
coluna por perfil. **A coluna do Admin Master é intocável** — ele tem acesso integral por garantia de
código, não por configuração. Só o master abre a matriz; toda concessão/revogação gera evento de
auditoria com antes/depois, e a instalação recusa ficar sem nenhum master ativo.

## Área administrativa

Aberto pelo menu **Administração** (ou `bussola ui --admin`) e só aparece para quem tem a permissão
de acesso; as seções aparecem conforme o perfil, então um Admin vê cinco e o master vê seis.

| Seção | O que faz |
|---|---|
| Visão geral | diagnóstico executado na hora: Python, PySide6, Argon2id, SQLite, versão do esquema, integridade, WAL, `synchronous`, espaço livre, tamanho real da base, contagens |
| Marca e tema | identidade da loja, logo PNG opcional, paleta com prévia de contraste (WCAG AA) e presets |
| Usuários | criar, ativar/desativar, trocar perfil (respeitando o nível) e redefinir senha |
| Perfis e permissões | matriz do que cada perfil pode fazer — exclusiva do Admin Master |
| Parâmetros | descontos, crediário, caixa e segurança, com faixa válida por parâmetro |
| Manutenção | cópia de segurança verificada, verificação de integridade/cadeia de auditoria, otimização e restauração (master) |

Nada ali é maquete: cada linha do diagnóstico vem de uma consulta ao ambiente ou ao banco, e o rodapé
informa quantas seções o perfil tem liberadas.

![Diagnóstico de dependências](docs/capturas/08_admin_dependencias.png)
![Marca e tema](docs/capturas/09_admin_marca.png)

## Instalação

Requer Python 3.12 ou superior.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
```

No Linux, o Qt precisa de bibliotecas de sistema
(`libxkbcommon0 libgl1 libegl1 libfontconfig1 libdbus-1-3`). No Windows, o PySide6 já traz o necessário.

## Uso rápido

```bash
# base fictícia completa + interface
bussola demo --banco dados/demo.db
bussola ui --banco dados/demo.db
# usuários: master / admin / gerente / contabilidade / operador — senha: Bussola#2026

# base vazia com administrador (pergunta a senha ou usa BUSSOLA_SENHA_ADMIN)
bussola init --banco dados/bussola.db

# diagnóstico, relatório e cópia de segurança
bussola info --banco dados/demo.db
bussola fechamento --banco dados/demo.db --data 2026-11-11
bussola backup --banco dados/demo.db --destino copias/
```

Sem instalar o pacote: `PYTHONPATH=src python -m bussola_pdv.cli <comando>`.

## Desenvolvimento

```bash
make test        # pytest (Qt em modo offscreen)
make lint        # ruff
make tipos       # mypy
make capturas    # gera docs/capturas/*.png sem servidor gráfico
make limpar      # remove caches
```

Atalhos na tela de PDV: `F2` foca o código, `Enter` adiciona, `Del` remove o item selecionado,
`F4` finaliza, `F6` cancela o cupom, `Esc` limpa a mensagem.

## Estrutura

```
src/bussola_pdv/
  dominio/         regras puras (dinheiro, venda, pagamentos, caixa, crediário, estoque, auditoria)
  aplicacao/       casos de uso, transações, autorização, relatórios
  infra/sqlite/    conexão, migrações versionadas, repositórios, massa demo
  ui/              PySide6: tema, login, PDV, caixa, consultas, fechamento
  ui/admin/        área administrativa: diagnóstico, marca, usuários, permissões, parâmetros, manutenção
  cli.py           linha de comando (init, demo, info, backup, fechamento, ui)
tests/             354 testes: unidade, integração com SQLite real, falhas e UI offscreen
docs/              análise do repositório de origem, decisões (ADRs), plano e capturas
```

## Limites explícitos

- **Não** é sistema fiscal e não emite NFC-e/SAT; a marca personalizada muda a interface e o rodapé
  do comprovante interno, nunca um documento fiscal.
- **Não** suporta vários computadores vendendo ao mesmo tempo; arquivo SQLite em rede não é suportado.
- A trilha de auditoria detecta adulteração, mas **não** impede um administrador do sistema de
  reescrever o banco inteiro.
- Pagamentos eletrônicos são registro manual; nenhuma integração bancária está homologada.
- Encargos de crediário, devolução parcial, PDF de fechamento, importação da planilha e empacotamento
  Windows **ainda não existem** (ver plano).

## O que é (e não é) o diretório `prototipo/`

`prototipo/especificacao/` guarda o material original: 23 documentos, 20 planilhas `.xlsx`, 5 módulos
VBA e 20 scripts que geraram as planilhas. Ele é referência histórica e de regra de negócio; a
aplicação não lê nem executa nada dali. Antes de abrir qualquer planilha como se fosse o sistema,
leia [prototipo/README.md](prototipo/README.md).

## Licença

GPL-2.0-or-later — veja [LICENSE](LICENSE) e [NOTICE.md](NOTICE.md). As imagens de referência do
repositório de origem **não** foram incorporadas. O nome é marca tipográfica provisória; não há
logotipo aprovado.
