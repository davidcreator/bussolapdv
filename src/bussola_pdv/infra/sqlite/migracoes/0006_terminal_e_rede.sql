-- Bússola Sistema PDV Open Source
-- Migração 0006 — identidade de terminal na venda e no turno (rede multi-caixa).
--
-- Com um servidor central e vários caixas, "quem fez isso" deixa de ser óbvio: a
-- base é uma só e a mesma pessoa pode operar em qualquer balcão. A coluna guarda o
-- identificador do terminal que fez a operação (`CAIXA-01`, `BALCAO-2`…).
--
-- Migração aditiva: bancos antigos ficam com '' (vazio), e o programa trata vazio
-- como "caixa local" — nada do histórico é reescrito.

ALTER TABLE vendas ADD COLUMN terminal_id TEXT NOT NULL DEFAULT '';
ALTER TABLE turnos ADD COLUMN terminal_id TEXT NOT NULL DEFAULT '';

-- Relatório "por terminal" (e a conferência de fechamento) filtra por dia e caixa.
CREATE INDEX ix_vendas_terminal ON vendas (terminal_id, data_negocio);
CREATE INDEX ix_turnos_terminal ON turnos (terminal_id, data_negocio);
