# Bússola Sistema PDV Open Source

Especificação de projeto para uma aplicação desktop offline.

**Estado: planejamento.** Este repositório contém um prompt de implementação e documentação inicial; não contém ainda uma aplicação de PDV executável. A planilha de origem também é um protótipo não homologado. Não utilize qualquer componente para vendas reais sem implementação, testes, revisão fiscal e homologação.

## Visão
Criar uma aplicação desktop para varejo, em português do Brasil, com frente de caixa, produtos, estoque, vendas, caixa por turno, pagamentos divididos, contas a receber, clientes, compras, fechamento, dashboard e auditoria. Operação local e offline é o padrão; importação da planilha é opcional, validada e não destrutiva.

## Comece por aqui
1. [`PROMPT_MESTRE_PYTHON.md`](PROMPT_MESTRE_PYTHON.md): briefing completo para implementar a aplicação.
2. [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md): arquitetura, dados e transações.
3. [`docs/REGRAS_NEGOCIO.md`](docs/REGRAS_NEGOCIO.md): políticas, cálculos e casos especiais.
4. [`docs/PLANO_TESTES.md`](docs/PLANO_TESTES.md): testes de aceitação e critérios de produção.
5. [`docs/OPERACAO.md`](docs/OPERACAO.md): instalação, uso, backup e recuperação planejados.
6. [`docs/IDENTIDADE_PROJETO.md`](docs/IDENTIDADE_PROJETO.md): nome oficial e identificadores técnicos propostos.
7. [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md) e [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md): governança inicial.

## Decisões iniciais
- Python 3.12+, PySide6/Qt Widgets e SQLite local; versão mínima definitiva e dependências serão fixadas quando houver implementação e testes. As dependências e a distribuição precisam de revisão de licenças, inclusive obrigações de Qt/PySide6 e bibliotecas empacotadas.
- Um arquivo SQLite local atende um único computador e vários operadores/turnos sequenciais. **Não** é uma solução multi-caixa simultânea em rede. Para várias estações, será necessário serviço local central e banco adequado, projeto separado e testes de concorrência.
- Valores monetários são armazenados em centavos inteiros; quantidades usam escala inteira por unidade definida, sem ponto flutuante binário.
- Venda, pagamentos, estoque, títulos e auditoria devem ser gravados atomicamente; cancelamentos e correções usam eventos reversos rastreáveis.
- Sem emissor fiscal automático até existir integração legalmente validada. O aplicativo não substitui contador ou sistema fiscal certificado.

## Instalação e execução
Ainda não disponíveis. Não há comandos de instalação, executáveis, testes automatizados ou releases publicados nesta entrega. Os procedimentos definitivos devem ser documentados depois da implementação e executados nas plataformas suportadas.

## Contribuições e segurança
Leia [CONTRIBUTING.md](CONTRIBUTING.md) antes de propor mudanças e [SECURITY.md](SECURITY.md) antes de relatar vulnerabilidades. Não inclua senhas, dados de clientes, bases reais, comprovantes, backups ou chaves no repositório.

## Licença
Proposta: **GNU General Public License versão 2 ou, a seu critério, qualquer versão posterior**, SPDX `GPL-2.0-or-later`. Veja [LICENSE](LICENSE) e [NOTICE.md](NOTICE.md). O titular dos direitos deve confirmar que pode licenciar suas contribuições e os materiais incorporados. Esta documentação não constitui parecer jurídico.
