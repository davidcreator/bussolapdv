-- Bússola Sistema PDV Open Source
-- Migração 0005 — encargos de atraso cobrados no recebimento, como receita separada.
-- sem-foreign-keys
--
-- Decisão (ADR-033): o título guarda o valor original. Multa e juros são
-- cobrados **junto** com a parcela, mas registrados em colunas próprias no
-- recebimento e num movimento de caixa próprio — assim o fechamento mostra
-- quanto entrou de mercadoria e quanto entrou de encargo, sem reescrever
-- histórico nem inflar o principal.

ALTER TABLE recebimentos ADD COLUMN multa_centavos INTEGER NOT NULL DEFAULT 0
    CHECK (multa_centavos >= 0);
ALTER TABLE recebimentos ADD COLUMN juros_centavos INTEGER NOT NULL DEFAULT 0
    CHECK (juros_centavos >= 0);
ALTER TABLE recebimentos ADD COLUMN encargo_centavos INTEGER NOT NULL DEFAULT 0
    CHECK (encargo_centavos >= 0);
ALTER TABLE recebimentos ADD COLUMN dias_atraso INTEGER NOT NULL DEFAULT 0
    CHECK (dias_atraso >= 0);
-- 1 = havia encargo devido e a loja dispensou (com autorização e motivo).
ALTER TABLE recebimentos ADD COLUMN encargos_dispensados INTEGER NOT NULL DEFAULT 0
    CHECK (encargos_dispensados IN (0, 1));

-- O caixa precisa de um tipo próprio para o dinheiro de encargo. O CHECK da
-- tabela original não aceita valor novo, então a tabela é reconstruída — o
-- SQLite não permite alterar CHECK no lugar.
CREATE TABLE movimentos_caixa_novo (
    id              TEXT PRIMARY KEY,
    turno_id        TEXT NOT NULL REFERENCES turnos (id),
    tipo            TEXT NOT NULL CHECK (tipo IN (
                        'VENDA_DINHEIRO', 'RECEBIMENTO_TITULO', 'RECEBIMENTO_ENCARGOS',
                        'SUPRIMENTO', 'SANGRIA', 'ESTORNO_DINHEIRO')),
    valor_centavos  INTEGER NOT NULL CHECK (valor_centavos > 0),
    venda_id        TEXT REFERENCES vendas (id),
    titulo_id       TEXT,
    motivo          TEXT NOT NULL DEFAULT '',
    autorizador_id  TEXT REFERENCES usuarios (id),
    criado_em       TEXT NOT NULL
);

INSERT INTO movimentos_caixa_novo (id, turno_id, tipo, valor_centavos, venda_id, titulo_id,
                                   motivo, autorizador_id, criado_em)
SELECT id, turno_id, tipo, valor_centavos, venda_id, titulo_id, motivo, autorizador_id, criado_em
  FROM movimentos_caixa;

DROP TABLE movimentos_caixa;
ALTER TABLE movimentos_caixa_novo RENAME TO movimentos_caixa;
CREATE INDEX ix_mov_caixa_turno ON movimentos_caixa (turno_id, tipo);
