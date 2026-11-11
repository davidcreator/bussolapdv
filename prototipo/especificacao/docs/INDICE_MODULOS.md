# Mapa dos módulos e telas da aplicação

> **Projeto:** Bússola Sistema PDV Open Source

Este é um plano de implementação, não um inventário de funcionalidades prontas. O visual deve seguir os princípios do prompt, adaptado a uma aplicação desktop e sem copiar marcas de terceiros.

| Módulo | Tela / recursos necessários | Dependências principais |
|---|---|---|
| Instruções | Onboarding, atalhos verificados, glossário, ajuda local e versão | Documentação distribuída offline |
| Parâmetros | Empresa, regras, formas, operadores, turnos e limites | Permissões e políticas auditadas |
| Produtos | Cadastro, busca, indicadores e alertas de estoque | Produtos, custos e movimentos |
| PDV | Carrinho, leitura de código, descontos, pagamentos e finalização | Autenticação, caixa, estoque e crédito |
| Vendas | Histórico, filtros, status e cancelamento controlado | Venda, autorização e auditoria |
| Itens de venda | Detalhe histórico por cupom, custo e quantidade | Venda e custos congelados |
| Caixa | Abertura, turnos, sangria, suprimento e contagem | Caixa físico, usuário e pagamentos |
| Pagamentos | Detalhe, status, taxas e conciliação | Venda, forma e confirmação externa |
| Fechamento | Quebra por forma, operador e turno, snapshot e PDF | Vendas, caixa, auditoria e pagamentos |
| Crediário | Parcelas, pagamentos parciais, aging e limite | Cliente, venda, recebimentos e política |
| Clientes | Cadastro, documentos, limites e revisão | Identificadores estáveis e privacidade |
| Estoque | Entradas, saídas, perda, ajustes e estornos | Produto e eventos de origem |
| Entradas | Fornecedor, nota, itens e rateio de frete | Estoque e custo histórico |
| Dashboard | Indicadores, filtros e gráficos locais | Fontes reconciliadas e escopos definidos |
| Auditoria | Eventos, investigação e relatórios de exceção | Identidade, correlação e retenção |
| Administração de listas | Domínios configuráveis com controle de impacto | Permissões, compatibilidade e testes |

A migração das 16 abas da planilha não deve replicar fórmulas ou intervalos fixos; cada módulo deve ter contratos de domínio e dados testáveis. O material da planilha foi desenvolvido como protótipo e contém limitações explicitadas no histórico de documentação, especialmente funções não integradas ou não homologadas.
