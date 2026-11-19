# Plano de implementação e estado real

Correspondência entre a sequência de 10 etapas do `PROMPT_MESTRE_PYTHON.md` e o que existe neste
repositório. **Nada é marcado como pronto sem teste executado.**

| Etapa do prompt mestre | Estado | Evidência |
|---|---|---|
| 1. Esqueleto, CI e banco com migrações | **Implementado e testado** | `pyproject.toml`, `.github/workflows/ci.yml`, `infra/sqlite/migracoes/`, `tests/test_persistencia_seguranca.py` |
| 2. Autenticação, permissões, parâmetros, produtos e clientes | **Implementado e testado** | `dominio/seguranca.py`, `dominio/usuario.py` (5 perfis), `aplicacao/autenticacao.py`, `aplicacao/permissoes.py`, telas administrativas de usuários/permissões/parâmetros, cadastros de produto/cliente + telas de produtos |
| 3. Estoque e entradas de fornecedor | **Parcial** | movimentos assinados, saldo, rateio de frete, entrada transacional e testes; **sem tela de entradas** e sem importação de XML de NF-e |
| 4. Caixa por turno e frente PDV | **Implementado e testado** | `aplicacao/caixa.py`, `aplicacao/pdv.py`, telas de caixa e PDV, testes de atomicidade e idempotência |
| 5. Pagamentos divididos, cartão/PIX e recebíveis | **Parcial** | split de 3 formas, troco, status pendente/confirmado e relatório de pendências; **sem integração TEF/adquirente** e sem recebíveis detalhados |
| 6. Crediário, parcelas, pagamentos parciais, limites | **Implementado e testado** | `dominio/crediario.py`, `aplicacao/crediario.py`, aging, limite e atraso; **sem tela própria** (aparece em fechamento) |
| 7. Cancelamentos, devoluções e auditoria append-only | **Parcial** | cancelamento com estorno e trilha com hash; **devolução parcial de itens não implementada** |
| 8. Fechamento, dashboard e PDF | **Parcial** | fechamento do dia com snapshot versionado + dashboard em texto/dados; **sem PDF e sem gráficos** |
| 9. Backup/restore, migração de dados e empacotamento | **Parcial** | backup consistente com verificação, restauração testada e expostos na tela de manutenção; **sem empacotamento** e sem importação de planilha |
| 10. QA, revisão de segurança/licenças/fiscal e homologação | **Não iniciado** | depende das decisões pendentes (`docs/DECISOES.md`) |

## Módulos da especificação

| Módulo | Estado |
|---|---|
| PDV | Funcional (carrinho, código/EAN, desconto, split, troco, autorização, atalhos) |
| Caixa | Funcional (abrir, sangria, suprimento, contagem, fechar) |
| Produtos | Consulta e indicadores funcionais; cadastro pela API (tela de cadastro pendente) |
| Vendas | Histórico e cancelamento funcional |
| Fechamento | Funcional em tela, snapshot e exportação Excel/PDF |
| Auditoria | Consulta e verificação de cadeia funcionais |
| Clientes | Tela de consulta + exportação (v0.6.0); cadastro pela API |
| Crediário | Tela de consulta + exportação; recebimento pela API (sem botão) |
| Estoque | Tela de saldos + exportação; movimentos e entrada pela API |
| Entradas | API funcional; tela pendente |
| Parâmetros | Tela administrativa com faixa por parâmetro (admin) |
| Administração | Funcional: diagnóstico, marca/tema, usuários, matriz de permissões, manutenção |
| Instruções / Dashboard gráfico | Pendentes (a casca e os indicadores por tela já existem) |

## Evidências da entrega administrativa

- `tests/test_hierarquia_permissoes.py` (41 testes): níveis, `pode_gerenciar`, `pode_receber_perfil`,
  concessão/revogação auditada, master único, autoelevação recusada, DELETE bloqueado por trigger.
- `tests/test_marca_tema.py` (31): paletas, contraste WCAG AA, presets, validação de CNPJ/logo,
  ida-e-volta por parâmetros, auditoria de marca e de tema, folha de estilo gerada.
- `tests/test_administracao.py` (23): diagnóstico real, integridade, cópia verificada, cópia corrompida
  recusada, restauração exclusiva do master e cópia do estado anterior.
- `tests/test_migracao_hierarquia.py` (7): migração `0003` com venda/turno apontando para usuário,
  `foreign_key_check` limpo, triggers e índice recriados, CHECK novo aceitando só os cinco perfis.
- `tests/test_ui_admin.py` (29): seções por perfil, matriz intocável na coluna do master, criação de
  usuário pela tela, edição de parâmetro, tema aplicado na janela principal e perda de acesso na sessão.

## Evidências da entrega de interface

- `tests/test_ui_adminlte.py` (27): ícones (cor, tamanho, cache, nome inválido), `Cartao`,
  `CaixaInfo`, `Selo`, `BarraLateral` (recolher, sinais, identidade), `BarraSuperior`,
  `PilhaDePaginas` (altura por página), folha de estilo (cartões, paleta, contraste) e casca da janela.
- `docs/INTERFACE.md`: tokens de cor, componentes, ícones, regras e capturas.
- 15 capturas em `docs/capturas/`, geradas offscreen por `make capturas`.

## Evidências da responsividade (v0.7.0)

- `tests/test_ui_responsivo.py` (25): réguas de largura nas bordas (899/900, 1179/1180) e refluência
  dos indicadores 4 → 3 → 2 → 1; altura da grade acompanhando as linhas (regressão da sobreposição);
  cabeçalho de cartão empilhando ferramentas e deixando de impor 949 px de mínimo; `CascaResponsiva`
  recolhendo a sidebar no compacto, respeitando a escolha manual até mudar de faixa e reduzindo margens;
  trilha e rodapé sumindo; `ColunasDaTabela` esticando quando cabe e entrando em modo rolagem quando
  não cabe, com piso de coluna e vigia único por tabela; `FluxoDeAcoes` quebrando a fileira de botões
  em linhas (com `heightForWidth`); `GradeDeCartoes` empilhando identidade/prévia; `ajustar_dialogo()`
  limitando à tela.
- **Medição real** (`make responsivo`, saída em 2026-11-11): `JanelaPrincipal` 800×600 → faixa
  compacta, sidebar recolhida, indicadores 2 por linha; 1024×768 → média, 3 por linha; 1280×800,
  1366×768 e 1920×1080 → ampla, 4 por linha. `JanelaAdmin` idem. Nenhuma página pediu mais largura do
  que a área disponível e nenhuma coluna desceu do mínimo legível — **OK nas cinco resoluções**.
- Conferência visual das seções administrativas em 800×600 (Marca, Usuários, Parâmetros, Manutenção):
  os botões de ação quebram em duas linhas e a seção rola na vertical, sem corte lateral.
- Capturas `21_pdv_800x600.png`, `22_produtos_800x600.png` e `23_caixa_800x600.png` ao lado das de
  1280×820, e `docs/DECISOES.md` ADR-021.
- **Não verificado**: uso real em tela de toque e em Windows com DPI acima de 100% (o layout é medido em
  pixels lógicos; a escala do sistema é aplicada pelo Qt, mas não foi testada em hardware).

## Evidências da correção do primeiro uso e da pasta de dados (v0.6.1)

- `tests/test_caminhos_instalacao.py` (23): precedência `BUSSOLA_DADOS` > escolha > padrão; criação e
  validação da pasta escolhida (recusa pasta sem escrita **antes** de criar banco); configuração
  corrompida cai no padrão; ponteiro fora da pasta de dados; subpastas (relatórios, cópias, logs)
  acompanham a escolha; log com traceback, rotação e `excepthook` idempotente; seção de Manutenção
  mostrando a pasta, trocando e auditando, e botão desabilitado para quem não é Admin Master.
- `tests/test_primeiro_uso.py` (20, eram 12): criar na pasta escolhida e gravar a escolha; pasta vazia
  e pasta sem permissão com mensagem; **erro inesperado visível na tela e no log** (regressão do
  "cliquei e nada aconteceu"); estado "Criando instalação…" no botão; base sem esquema avisa
  instalação incompleta; base corrompida é guardada como `pdv.db.antigo-*` e a instalação recomeça;
  base válida não é tocada; `entrada.main` usa a base da pasta escolhida.
- Captura `20_primeiro_uso.png` e `docs/DECISOES.md` ADR-020.

## Evidências da entrega de clientes, crediário e estoque (v0.6.0)

- `tests/test_exportacao_modulos.py` (27): carteira de clientes com limite/em aberto/disponível/vencido,
  documento **mascarado** no arquivo, busca que filtra, **título `PARCIAL` contado no saldo** (regressão),
  crediário com e sem `incluir_pagos`, colunas do título, posição de estoque por produto, ruptura somada
  no resumo, busca por código, relatório do turno aberto (fundo, movimentos, autorizador resolvido),
  turno fechado com contagem por denominação e classificação da diferença, erro sem turno aberto,
  `.xlsx` lido por `openpyxl` e `.pdf` por `pypdf` nos quatro relatórios, evento `DADOS_EXPORTADOS` com
  autor e formato, atendente sem permissão, e CLI (`clientes`, `turno`, `crediario --incluir-pagos`,
  saída 2 sem turno aberto).
- `tests/test_ui_telas_modulos.py` (12): tabela da tela idêntica ao relatório (linha a linha), busca
  reduzindo linhas, KPIs preenchidos, botão Exportar visível só para gerente e gravando arquivo, caixa
  "incluir recebidos" aumentando as linhas, estoque por busca, **Exportar do turno** habilitado com
  turno aberto e desabilitado sem turno, e os três módulos deixando de ser placeholder na janela.
- Capturas `16_clientes`, `17_crediario`, `18_estoque` e `19_caixa_exportar` (sessão de gerente).
- `docs/DECISOES.md` ADR-019 (tela desenha o relatório) e `docs/EXPORTACAO.md` com os quatro relatórios
  novos.

## Evidências da entrega de exportação (v0.5.0)

- `tests/test_exportacao.py` (41): modelo (`Relatorio`/`Tabela`/`Coluna`, validações, nome de arquivo,
  slug, tipos), formatação pt-BR (moeda, centavos→reais sem resíduo, data ISO→BR), escritor `.xlsx`
  (partes do pacote, **leitura por openpyxl** conferindo moeda como número, data como data, texto
  escapado, aba saneada/única, filtro automático, painel congelado, larguras, planilha vazia),
  escritor `.pdf` (**leitura por pypdf**: `%PDF`, `%%EOF`, título, rodapé `página X de Y`, 400 linhas
  em várias páginas, escape de HTML), serviço (valores iguais aos da tela, permissão negada para
  atendente, contabilidade exporta, evento `DADOS_EXPORTADOS`, cadeia de hashes íntegra, loja/CNPJ no
  cabeçalho, aviso fiscal em todos os relatórios) e CLI (sucesso em PDF, nome sugerido em pasta,
  senha errada, perfil sem permissão, falta de `--data`, banco inexistente).
- `tests/test_ui_exportacao.py` (13): menu com os dois formatos, botão oculto para atendente,
  exportação gravando arquivo e emitindo sinal, extensão corrigida, cancelamento sem arquivo, as
  quatro telas com o botão, fechamento exportando o dia escolhido e catálogo respeitando a busca.
- `docs/EXPORTACAO.md` + exemplos versionados (`docs/exemplos/fechamento-exemplo.pdf` e `.xlsx`,
  gerados por `ferramentas/gerar_exemplos.py` a partir de `bussola demo`).

## Evidências da entrega de instalação Windows (v0.4.0)

- `tests/test_primeiro_uso.py` (10): detecção de base ausente/vazia/pronta/arquivo corrompido;
  diálogo cria Admin Master, `Caixa 1` e nome da loja pelos casos de uso do `init`; senhas divergentes,
  campos vazios e senha curta recusados sem deixar base criada.
- `tests/test_empacotamento.py` (21): versão de `versao_info.txt`, `pyproject.toml` e `instalador.iss`
  sincronizadas com `__version__`; `.ico` com 7 resoluções e PNGs válidos; spec aponta para arquivos
  existentes; `.iss` só referencia arquivos reais e não apaga dados na desinstalação; workflow publica
  `.zip` e `setup.exe`; diretório de dados por sistema (`LOCALAPPDATA`, `XDG_DATA_HOME`, `BUSSOLA_DADOS`);
  `bussola-pdv` com argumento devolve o controle ao CLI.
- **Build de fumaça real** (Linux, mesma receita do spec): `python -m PyInstaller empacotamento/bussola.spec`
  produziu um binário congelado que executou `demo` (base criada), `info` (esquema v3, integridade OK,
  cadeia de auditoria íntegra em 42 eventos) e `--version`. O teste pegou um defeito real: as migrações
  `.sql` não estavam no bundle e o executável falhava com `no such table: usuarios` — corrigido em
  `datas` do spec, com teste de regressão.
- `docs/INSTALACAO_WINDOWS.md`: três caminhos (instalador, código, build), pacotes pip por extra,
  pasta de dados, backup/restauração, SmartScreen, desinstalação, problemas comuns e checklist.
- **Não verificado**: binário Windows (`.exe`), instalador `.iss` compilado e instalação em Windows real
  — exigem runner `windows-latest` (workflow `windows.yml`) ou máquina Windows.

## Evidências da entrega de encargos, nuvem e rede (v0.14.0)

- Encargos: `tests/test_encargos_cobranca.py` (12) e `tests/test_migracao_encargos.py` provam multa,
  juros, carência, dispensa com autorizador e motivo, `RECEBIMENTO_ENCARGOS` no caixa, separação no
  resumo do turno e o título **sem** valor reescrito.
- Nuvem: `tests/test_nuvem_clientes.py` (17) assina contra as duas especificações (vetor oficial da
  AWS e exemplo da Microsoft), envia/baixa/lista/remove contra um servidor local que **exige** a
  assinatura, e cobre o caminho do `bussola backup --nuvem` com a nuvem fora do ar (código 2, cópia
  local intacta).
- Rede: `tests/test_rede_multi_caixa.py` (16) sobe o servidor em **HTTPS real** com o certificado
  gerado pelo programa, recusa cliente que não confia no certificado, prova a digital SHA-256, o
  reaproveitamento do certificado, o terminal no cabeçalho chegando ao banco, o log JSONL, entrada de
  estoque, recebimento com encargo, e a **corrida do último item** (uma venda aceita, a outra
  recusada, estoque 0). O mesmo arquivo cobre a recusa de `0.0.0.0` sem TLS.
- **Não verificado nesta entrega**: instalação do `.crt` como confiável nas máquinas Windows
  (P16) e a tela do caixa remoto (não existe ainda, por decisão).

## Evidências da entrega do caixa remoto (v0.15.0)

- **Executor e contrato**: `tests/test_modo_remoto.py` (30) sobe servidor com TLS de verdade e prova
  que a tela do caixa vende pela rede — sessão, busca de produto, carrinho, plano e venda gravada com
  o `terminal_id` do caixa; erro de negócio chegando ao balcão como o mesmo tipo do domínio;
  identidade **descartada** quando o terminal tenta operar em nome de outro usuário; autorização de
  gerente conferida no servidor; e certificado de outro servidor **recusado** mesmo com a máquina no
  ar. O teste achou dois defeitos reais, corrigidos: o terminal mandava `self` como argumento (422) e
  `DELETE /v1/sessao` respondia 501.
- **Fila offline**: `tests/test_fila_offline.py` (5) prova que a venda guardada volta pela mesma
  `chave_idempotencia` (reenviar duas vezes não duplica), que recusa de negócio vira pendência com
  motivo (não é apagada) e que descartar é ato explícito. Sessão vencida por reinício do servidor
  **não** marca a venda como recusada.
- **Telas**: `tests/test_ui_modo_terminal.py` (10) abre as telas de verdade (Qt offscreen): o primeiro
  uso só libera "Confiar e usar" depois de verificar o servidor, mostra a digital correta, grava
  `terminal.json` + `servidor-do-caixa.crt`; a `JanelaPrincipal` em modo remoto lista os módulos
  (com a entrada nova **Vendas pendentes**), navega em Produtos/Vendas/Auditoria pela rede **sem base
  local**, e a tela de pendências reenvia uma venda guardada até ela aparecer na base do servidor.
- **Retrocompatibilidade**: os 27 arquivos de `ui/` passaram a usar `servicos_de(contexto)`; a suíte
  inteira continua verde no modo local (**1053 testes**, baseline anterior 1010).
- **Não verificado nesta entrega**: dois caixas reais numa loja, latência em rede saturada e o
  comportamento da fila com dezenas de vendas pendentes.

## Próximos incrementos sugeridos (ordem)

1. ~~Telas de clientes, crediário e estoque~~ — feito na v0.6.0 (consulta e exportação).
   ~~Escolher a pasta de dados~~ — feito na v0.6.1. ~~Responsividade~~ — feito na v0.7.0.
2. ~~**Operação nas telas novas**: cadastrar/editar produto e cliente, receber título e lançar
   entrada/ajuste de estoque com formulário~~ — feito na v0.12.0, junto com a página **Entradas**,
   que deixou de ser placeholder (só **Parâmetros** continua marcado).
3. ~~Devolução parcial de venda~~ — feito na v0.13.0 com tipo (arrependimento, defeito, garantia,
   erro), prazo conferido e destino do valor (dinheiro, crédito no crediário, troca).
   **Pontos de construção** abertos na mesma versão, com documento e contrato: fiscal
   (`docs/FISCAL.md`), rede multi-caixa (`docs/REDE.md`), nuvem AWS/Azure (`docs/NUVEM.md`) e
   encargos de atraso (`docs/ENCARGOS.md`).
4. ~~**Encargos cobrados, nuvem de verdade e servidor de rede utilizável**~~ — feito na v0.14.0
   (ADR-033, ADR-034, ADR-035): cobrança de multa/juros como receita separada e desligada de fábrica,
   clientes S3 e Azure em biblioteca padrão com `bussola backup --nuvem`, e API de escrita completa
   com HTTPS gerado pelo programa, terminal identificado, log de acesso e concorrência provada.
5. ~~**Tela do caixa remoto**~~ — feito na v0.15.0 (ADR-036): janela **completa** em modo cliente,
   configuração no primeiro uso com digital fixada e fila offline para a venda. O que resta é
   robustez de operação (token por terminal, relatório por caixa, teste de carga — `docs/REDE.md`,
   seção 4).
6. **Conta de nuvem e retenção** — clientes prontos, falta contratar e decidir quem guarda a chave.
7. Importação validada da planilha protótipo (pré-visualização + relatório de erros).
8. Assinatura digital dos binários Windows e hashes publicados na Release.
9. Revisão de segurança/LGPD e homologação com operador real.
