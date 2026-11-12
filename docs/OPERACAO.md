# Operação, instalação e recuperação — plano

> **Projeto:** Bússola Sistema PDV Open Source

Este documento descreve o que a versão futura deverá oferecer. Nenhuma operação abaixo está disponível ou testada nesta entrega.

## Preparação
Definir diretório de dados local, conta administradora, caixas, operadores, permissões, parâmetros de negócio e política fiscal. Criar usuários e configurar autenticação sem divulgar senha/PIN. Cadastre produtos, clientes e saldos iniciais após validação e backup. Dados de exemplo devem ser separados da base real.

## Rotina planejada
1. Operador autentica; gerente abre turno e informa fundo de troco.
2. Operador busca produto, informa quantidade, revisa desconto e total, escolhe pagamentos e confirma recebimentos pelos procedimentos da empresa.
3. O sistema registra venda e estoque de forma atômica; recebimentos de crediário são lançamentos distintos.
4. Ao final do turno, conte cédulas, registre divergências e encerre com responsável. Gere conferência diária e preserve evidências.
5. Faça backup consistente, proteja a cópia e teste restauração regularmente.

## Instalação e atualização
Comandos, versões suportadas e links serão preenchidos somente após o software e os pacotes existirem. Uma atualização deverá informar mudanças de esquema, backup obrigatório, compatibilidade e plano de rollback. Não execute arquivos não verificados.

## Recuperação
A implementação deve permitir backup consistente do SQLite e restauração em área isolada; verificar integridade e reconciliação de registros antes de trocar a base. Não copiar somente o arquivo principal enquanto há escrita ativa ou ignorando arquivos auxiliares do banco. Documentar criptografia e gestão de chaves caso implementadas.

## Suporte e segurança
O projeto ainda não possui canal de suporte configurado. Vulnerabilidades: siga `SECURITY.md`. Dúvidas fiscais e LGPD devem ser revisadas com profissionais habilitados.
