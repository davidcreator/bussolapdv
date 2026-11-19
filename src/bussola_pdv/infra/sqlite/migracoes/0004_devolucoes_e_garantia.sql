-- Migração 0004 — devoluções com tipo e destino, prazo de garantia do produto.
--
-- Por que uma tabela nova em vez de "desfazer" a venda: devolução é documento
-- próprio. A venda original continua inteira, com o que foi cobrado; a devolução
-- diz o que voltou, por qual motivo, dentro de qual prazo e para onde o valor foi
-- (dinheiro, crédito no crediário, troca). Somar as devoluções de uma venda é uma
-- consulta; o relatório de vendas não muda de significado.

ALTER TABLE produtos ADD COLUMN garantia_dias INTEGER NOT NULL DEFAULT 0
    CHECK (garantia_dias >= 0 AND garantia_dias <= 3650);

CREATE TABLE devolucoes (
    id                  TEXT PRIMARY KEY,
    venda_id            TEXT NOT NULL REFERENCES vendas (id),
    data_negocio        TEXT NOT NULL,
    criado_em           TEXT NOT NULL,
    operador_id         TEXT NOT NULL REFERENCES usuarios (id),
    autorizador_id      TEXT REFERENCES usuarios (id),
    tipo                TEXT NOT NULL CHECK (tipo IN (
                            'ARREPENDIMENTO', 'DEFEITO', 'GARANTIA', 'ERRO_OPERACIONAL'
                        )),
    destino             TEXT NOT NULL CHECK (destino IN (
                            'DINHEIRO', 'CREDITO_CREDIARIO', 'TROCA'
                        )),
    motivo              TEXT NOT NULL,
    observacoes         TEXT NOT NULL DEFAULT '',
    total_centavos      INTEGER NOT NULL CHECK (total_centavos > 0),
    dinheiro_centavos   INTEGER NOT NULL DEFAULT 0 CHECK (dinheiro_centavos >= 0),
    credito_centavos    INTEGER NOT NULL DEFAULT 0 CHECK (credito_centavos >= 0),
    estoque_devolvido   INTEGER NOT NULL DEFAULT 1 CHECK (estoque_devolvido IN (0, 1)),
    dias_desde_venda    INTEGER NOT NULL DEFAULT 0 CHECK (dias_desde_venda >= 0),
    fora_do_prazo       INTEGER NOT NULL DEFAULT 0 CHECK (fora_do_prazo IN (0, 1)),
    turno_id            TEXT REFERENCES turnos (id),
    chave_idempotencia  TEXT NOT NULL UNIQUE
);

CREATE INDEX ix_devolucoes_venda ON devolucoes (venda_id);
CREATE INDEX ix_devolucoes_data ON devolucoes (data_negocio);

CREATE TABLE devolucao_itens (
    id                      TEXT PRIMARY KEY,
    devolucao_id            TEXT NOT NULL REFERENCES devolucoes (id),
    venda_item_sequencia    INTEGER NOT NULL CHECK (venda_item_sequencia > 0),
    produto_id              TEXT NOT NULL REFERENCES produtos (id),
    codigo                  TEXT NOT NULL,
    descricao               TEXT NOT NULL,
    quantidade_milesimos    INTEGER NOT NULL CHECK (quantidade_milesimos > 0),
    valor_unitario_centavos INTEGER NOT NULL CHECK (valor_unitario_centavos >= 0),
    total_centavos          INTEGER NOT NULL CHECK (total_centavos >= 0)
);

CREATE INDEX ix_devolucao_itens_devolucao ON devolucao_itens (devolucao_id);
CREATE INDEX ix_devolucao_itens_produto ON devolucao_itens (produto_id);

-- Devolução é histórico: corrige-se com outro documento (ou com estorno), nunca
-- com UPDATE/DELETE. Mesma trava que a trilha de auditoria usa.
CREATE TRIGGER tg_devolucoes_sem_update
BEFORE UPDATE ON devolucoes BEGIN
    SELECT RAISE(ABORT, 'Devolução não pode ser alterada; registre outra.');
END;

CREATE TRIGGER tg_devolucoes_sem_delete
BEFORE DELETE ON devolucoes BEGIN
    SELECT RAISE(ABORT, 'Devolução não pode ser excluída; registre outra.');
END;

CREATE TRIGGER tg_devolucao_itens_sem_update
BEFORE UPDATE ON devolucao_itens BEGIN
    SELECT RAISE(ABORT, 'Item de devolução não pode ser alterado.');
END;

CREATE TRIGGER tg_devolucao_itens_sem_delete
BEFORE DELETE ON devolucao_itens BEGIN
    SELECT RAISE(ABORT, 'Item de devolução não pode ser excluído.');
END;
