# Como contribuir

> **Projeto:** Bússola Sistema PDV Open Source

Obrigado pelo interesse. Este projeto está em planejamento; os procedimentos de build, testes e CI serão acrescentados quando houver código. Não declare testes executados sem evidência.

## Processo
1. Antes de mudanças grandes, abra uma issue com problema, contexto, proposta e impacto. Não publique dados pessoais, credenciais, comprovantes ou arquivos reais.
2. Crie uma branch descritiva a partir da branch principal. Mantenha mudanças focadas, com migração de dados e documentação quando necessário.
3. Ao existir código, execute formatação, lint, análise de tipos e testes conforme os comandos documentados naquela versão. Acrescente testes de sucesso, erro, permissão e rollback para regras de negócio alteradas.
4. Atualize CHANGELOG, documentação de operação e segurança conforme o impacto. Abra um pull request usando o modelo; informe o que foi efetivamente testado e o que não foi.
5. Aguarde revisão. Mantenedores podem solicitar alterações, rejeitar uma contribuição ou exigir homologação fiscal/segurança.

## Regras de contribuição
- Você deve ter autorização para contribuir e licenciar o material sob GPL-2.0-or-later; não envie código, fonte, imagens ou datasets de licença incompatível.
- Inclua cabeçalho SPDX em novos arquivos-fonte quando houver titularidade apropriada; não invente titular, autor ou data. Veja NOTICE.md.
- Não adicione segredos, dados reais, backups, binários opacos ou dependências não revisadas. Use dados inteiramente fictícios.
- Mudanças financeiras devem usar precisão exata, testes de arredondamento e rastreabilidade. Não apague histórico nem ignore falhas.
- Siga o código de conduta. Vulnerabilidades devem seguir SECURITY.md, não uma issue pública.

## Convenções recomendadas
Código em inglês ou português consistente, mensagens de interface em pt-BR, nomes de IDs sem dados pessoais, type hints e docstrings quando úteis. Estilo, versões de ferramentas e comandos exatos serão definidos com o código. Pull requests devem descrever compatibilidade, migrações e rollback quando aplicável.
