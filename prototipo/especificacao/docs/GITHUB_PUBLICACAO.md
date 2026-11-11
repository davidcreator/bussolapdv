# Checklist para publicação no GitHub

> **Projeto:** Bússola Sistema PDV Open Source

Estado: preparação local; o repositório ainda não foi criado, configurado ou publicado no GitHub.

## Antes de publicar
- [x] Nome oficial definido: **Bússola Sistema PDV Open Source**.
- [ ] Confirmar o identificador técnico e a disponibilidade do nome no GitHub; sugestão provisória: `bussola-sistema-pdv`.
- [ ] Definir descrição, titulares de direitos e ano. Confirmar que a organização pode licenciar todo o conteúdo como GPL-2.0-or-later.
- [ ] Revisar código e ativos de terceiros, licenças e notices, inclusive Qt/PySide6, fontes, imagens e empacotador. Não publicar as imagens de referência sem permissão.
- [ ] Verificar ausência de dados reais, CPF/CNPJ de clientes, segredos, bancos, planilhas de operação e arquivos de backup. `.gitignore` não remove segredos já rastreados.
- [ ] Revisar README, NOTICE e informações reais de suporte; configurar canal privado de conduta e divulgação de segurança.
- [ ] Criar o repositório no GitHub e confirmar que o arquivo LICENSE e o identificador GPL-2.0-or-later aparecem corretamente na documentação. A detecção automática pode exibir GPL-2.0 em razão do texto padrão; confirme a expressão `-or-later` em README, NOTICE e cabeçalhos.
- [ ] Habilitar relatórios privados de vulnerabilidade em Security, se disponíveis, e definir política de resposta.
- [ ] Definir mantenedores, regras de branch, revisão de pull request, permissões mínimas e uso de MFA.
- [ ] Validar templates de issues e pull request. Labels são sugeridas e devem existir no repositório se desejado.
- [ ] Quando houver código, criar CI com teste, lint, tipagem e análise de dependências; usar versões fixadas e permissões mínimas. Não adicionar workflow que finja executar testes ausentes.
- [ ] Adicionar revisão de dependências e secret scanning quando disponíveis no plano/configuração; tratar alertas.
- [ ] Criar release somente após build reproduzível tanto quanto possível, licenças, hashes, testes e homologação. Não publicar dados de teste pessoais.

## Local e envio
Os comandos Git dependem do nome escolhido para o repositório e das credenciais do responsável. Inicialize o repositório, revise `git status` e o diff, faça commit e configure o remoto correto. Não insira credenciais em arquivos do projeto ou histórico. A publicação e as configurações do GitHub exigem ação/autorização do responsável.
