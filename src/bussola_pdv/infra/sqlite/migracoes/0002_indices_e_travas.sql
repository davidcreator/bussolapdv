-- Bússola Sistema PDV Open Source
-- Migração 0002 — índices de relatório e salvaguardas adicionais.
-- Migração puramente aditiva: nenhuma coluna é removida nem renomeada.

-- Fechamento por forma e por turno consulta muito pagamentos por data comercial.
CREATE INDEX IF NOT EXISTS ix_vendas_data_turno ON vendas (data_negocio, turno_id, status);
CREATE INDEX IF NOT EXISTS ix_pagamentos_forma ON pagamentos (forma, status);

-- Recebimentos de títulos por data comercial (conciliação de caixa por turno).
CREATE INDEX IF NOT EXISTS ix_recebimentos_data ON recebimentos (data_negocio, turno_id);

-- Snapshot de fechamento não pode ser alterado depois de gravado.
CREATE TRIGGER IF NOT EXISTS tg_fechamento_sem_update
BEFORE UPDATE ON fechamentos
BEGIN
    SELECT RAISE(ABORT, 'Snapshot de fechamento é imutável; gere uma nova versão.');
END;

CREATE TRIGGER IF NOT EXISTS tg_fechamento_sem_delete
BEFORE DELETE ON fechamentos
BEGIN
    SELECT RAISE(ABORT, 'Snapshot de fechamento não pode ser excluído.');
END;

-- Itens de venda e pagamentos de venda concluída são imutáveis: correções usam
-- estorno auditado, nunca edição de histórico.
CREATE TRIGGER IF NOT EXISTS tg_itens_sem_update
BEFORE UPDATE ON itens_venda
BEGIN
    SELECT RAISE(ABORT, 'Itens de venda são histórico imutável.');
END;

CREATE TRIGGER IF NOT EXISTS tg_itens_sem_delete
BEFORE DELETE ON itens_venda
BEGIN
    SELECT RAISE(ABORT, 'Itens de venda são histórico imutável.');
END;
