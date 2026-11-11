-- Bússola Sistema PDV Open Source
-- Migração 0001 — esquema inicial
-- Convenções: dinheiro em centavos (INTEGER), quantidade em milésimos (INTEGER),
-- instantes em UTC ISO-8601 (TEXT), data comercial ISO (TEXT).
-- Nenhum valor monetário é REAL. Nenhuma exclusão de histórico é permitida.

CREATE TABLE esquema_versao (
    versao      INTEGER PRIMARY KEY,
    descricao   TEXT NOT NULL,
    aplicado_em TEXT NOT NULL
);

CREATE TABLE parametros (
    chave         TEXT PRIMARY KEY,
    valor         TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

CREATE TABLE usuarios (
    id                TEXT PRIMARY KEY,
    login             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nome              TEXT NOT NULL,
    perfil            TEXT NOT NULL CHECK (perfil IN ('OPERADOR', 'GERENTE', 'ADMINISTRADOR')),
    senha_hash        TEXT NOT NULL,
    ativo             INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    tentativas_falhas INTEGER NOT NULL DEFAULT 0 CHECK (tentativas_falhas >= 0),
    bloqueado_ate     TEXT,
    criado_em         TEXT NOT NULL
);

CREATE TABLE caixas (
    id         TEXT PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE,
    ativo      INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em  TEXT NOT NULL
);

CREATE TABLE turnos (
    id                TEXT PRIMARY KEY,
    caixa_id          TEXT NOT NULL REFERENCES caixas (id),
    operador_id       TEXT NOT NULL REFERENCES usuarios (id),
    data_negocio      TEXT NOT NULL,
    fundo_centavos    INTEGER NOT NULL CHECK (fundo_centavos >= 0),
    aberto_em         TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('ABERTO', 'FECHADO')),
    fechado_em        TEXT,
    conferente_id     TEXT REFERENCES usuarios (id),
    contado_centavos  INTEGER CHECK (contado_centavos IS NULL OR contado_centavos >= 0),
    diferenca_centavos INTEGER,
    motivo_diferenca  TEXT,
    CHECK (status = 'ABERTO' OR fechado_em IS NOT NULL)
);

-- Um único turno aberto por caixa física, garantido pelo banco.
CREATE UNIQUE INDEX ux_turno_aberto_por_caixa ON turnos (caixa_id) WHERE status = 'ABERTO';
CREATE INDEX ix_turnos_data ON turnos (data_negocio, status);

CREATE TABLE clientes (
    id                     TEXT PRIMARY KEY,
    nome                   TEXT NOT NULL,
    documento              TEXT,
    tipo_documento         TEXT CHECK (tipo_documento IN ('CPF', 'CNPJ')),
    limite_credito_centavos INTEGER NOT NULL DEFAULT 0 CHECK (limite_credito_centavos >= 0),
    ativo                  INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    observacoes            TEXT NOT NULL DEFAULT '',
    criado_em              TEXT NOT NULL
);

CREATE UNIQUE INDEX ux_cliente_documento ON clientes (documento) WHERE documento IS NOT NULL;
CREATE INDEX ix_clientes_nome ON clientes (nome);

CREATE TABLE produtos (
    id                       TEXT PRIMARY KEY,
    codigo                   TEXT NOT NULL UNIQUE,
    codigo_barras            TEXT UNIQUE,
    descricao                TEXT NOT NULL,
    categoria                TEXT NOT NULL DEFAULT '',
    unidade                  TEXT NOT NULL CHECK (unidade IN ('UN', 'KG', 'LT', 'CX', 'MT', 'DZ')),
    custo_centavos           INTEGER NOT NULL CHECK (custo_centavos >= 0),
    preco_centavos           INTEGER NOT NULL CHECK (preco_centavos > 0),
    estoque_minimo_milesimos INTEGER NOT NULL DEFAULT 0 CHECK (estoque_minimo_milesimos >= 0),
    ponto_pedido_milesimos   INTEGER NOT NULL DEFAULT 0 CHECK (ponto_pedido_milesimos >= 0),
    fornecedor               TEXT NOT NULL DEFAULT '',
    ncm                      TEXT NOT NULL DEFAULT '',
    ativo                    INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em                TEXT NOT NULL,
    atualizado_em            TEXT NOT NULL
);

CREATE INDEX ix_produtos_descricao ON produtos (descricao);
CREATE INDEX ix_produtos_categoria ON produtos (categoria, ativo);

CREATE TABLE sequencias (
    nome  TEXT PRIMARY KEY,
    valor INTEGER NOT NULL CHECK (valor >= 0)
);

INSERT INTO sequencias (nome, valor) VALUES ('venda', 0);

CREATE TABLE vendas (
    id                   TEXT PRIMARY KEY,
    numero               INTEGER NOT NULL,
    serie                TEXT NOT NULL DEFAULT '1',
    data_negocio         TEXT NOT NULL,
    criado_em            TEXT NOT NULL,
    operador_id          TEXT NOT NULL REFERENCES usuarios (id),
    cliente_id           TEXT REFERENCES clientes (id),
    turno_id             TEXT NOT NULL REFERENCES turnos (id),
    status               TEXT NOT NULL CHECK (status IN ('CONCLUIDA', 'CANCELADA')),
    subtotal_centavos    INTEGER NOT NULL CHECK (subtotal_centavos >= 0),
    desconto_centavos    INTEGER NOT NULL CHECK (desconto_centavos >= 0),
    acrescimo_centavos   INTEGER NOT NULL CHECK (acrescimo_centavos >= 0),
    total_centavos       INTEGER NOT NULL CHECK (total_centavos >= 0),
    custo_total_centavos INTEGER NOT NULL CHECK (custo_total_centavos >= 0),
    chave_idempotencia   TEXT NOT NULL UNIQUE,
    cancelada_em         TEXT,
    motivo_cancelamento  TEXT,
    autorizador_id       TEXT REFERENCES usuarios (id),
    UNIQUE (serie, numero),
    CHECK (status = 'CONCLUIDA' OR cancelada_em IS NOT NULL)
);

CREATE INDEX ix_vendas_data ON vendas (data_negocio, status);
CREATE INDEX ix_vendas_operador ON vendas (operador_id, data_negocio);
CREATE INDEX ix_vendas_turno ON vendas (turno_id, status);
CREATE INDEX ix_vendas_cliente ON vendas (cliente_id, data_negocio);

CREATE TABLE itens_venda (
    id                        TEXT PRIMARY KEY,
    venda_id                  TEXT NOT NULL REFERENCES vendas (id),
    sequencia                 INTEGER NOT NULL CHECK (sequencia > 0),
    produto_id                TEXT NOT NULL REFERENCES produtos (id),
    codigo_produto            TEXT NOT NULL,
    descricao                 TEXT NOT NULL,
    unidade                   TEXT NOT NULL,
    quantidade_milesimos      INTEGER NOT NULL CHECK (quantidade_milesimos > 0),
    preco_unitario_centavos   INTEGER NOT NULL CHECK (preco_unitario_centavos >= 0),
    desconto_centavos         INTEGER NOT NULL DEFAULT 0 CHECK (desconto_centavos >= 0),
    total_centavos            INTEGER NOT NULL CHECK (total_centavos >= 0),
    custo_unitario_centavos   INTEGER NOT NULL CHECK (custo_unitario_centavos >= 0),
    UNIQUE (venda_id, sequencia),
    CHECK (desconto_centavos <= quantidade_milesimos * preco_unitario_centavos / 1000 + 1)
);

CREATE INDEX ix_itens_venda_produto ON itens_venda (produto_id);

CREATE TABLE pagamentos (
    id                      TEXT PRIMARY KEY,
    venda_id                TEXT NOT NULL REFERENCES vendas (id),
    sequencia               INTEGER NOT NULL CHECK (sequencia > 0),
    forma                   TEXT NOT NULL CHECK (forma IN (
                                'DINHEIRO', 'PIX', 'DEBITO', 'CREDITO', 'CREDITO_PARCELADO',
                                'TRANSFERENCIA', 'VALE', 'CHEQUE', 'A_PRAZO')),
    valor_entregue_centavos INTEGER NOT NULL CHECK (valor_entregue_centavos >= 0),
    valor_aplicado_centavos INTEGER NOT NULL CHECK (valor_aplicado_centavos > 0),
    troco_centavos          INTEGER NOT NULL DEFAULT 0 CHECK (troco_centavos >= 0),
    status                  TEXT NOT NULL CHECK (status IN ('PENDENTE', 'CONFIRMADO', 'ESTORNADO')),
    confirmacao_manual      INTEGER NOT NULL DEFAULT 0 CHECK (confirmacao_manual IN (0, 1)),
    referencia              TEXT NOT NULL DEFAULT '',
    bandeira                TEXT NOT NULL DEFAULT '',
    nsu                     TEXT NOT NULL DEFAULT '',
    parcelas                INTEGER NOT NULL DEFAULT 1 CHECK (parcelas >= 1),
    criado_em               TEXT NOT NULL,
    UNIQUE (venda_id, sequencia),
    CHECK (troco_centavos = valor_entregue_centavos - valor_aplicado_centavos
           OR valor_entregue_centavos = valor_aplicado_centavos)
);

CREATE INDEX ix_pagamentos_venda ON pagamentos (venda_id, forma);

CREATE TABLE movimentos_caixa (
    id              TEXT PRIMARY KEY,
    turno_id        TEXT NOT NULL REFERENCES turnos (id),
    tipo            TEXT NOT NULL CHECK (tipo IN (
                        'VENDA_DINHEIRO', 'RECEBIMENTO_TITULO', 'SUPRIMENTO', 'SANGRIA', 'ESTORNO_DINHEIRO')),
    valor_centavos  INTEGER NOT NULL CHECK (valor_centavos > 0),
    venda_id        TEXT REFERENCES vendas (id),
    titulo_id       TEXT,
    motivo          TEXT NOT NULL DEFAULT '',
    autorizador_id  TEXT REFERENCES usuarios (id),
    criado_em       TEXT NOT NULL
);

CREATE INDEX ix_mov_caixa_turno ON movimentos_caixa (turno_id, tipo);

CREATE TABLE contagens_caixa (
    id                  TEXT PRIMARY KEY,
    turno_id            TEXT NOT NULL REFERENCES turnos (id),
    denominacao         INTEGER NOT NULL CHECK (denominacao > 0),
    quantidade          INTEGER NOT NULL CHECK (quantidade >= 0),
    criado_em           TEXT NOT NULL,
    UNIQUE (turno_id, denominacao)
);

CREATE TABLE movimentos_estoque (
    id                       TEXT PRIMARY KEY,
    produto_id               TEXT NOT NULL REFERENCES produtos (id),
    quantidade_milesimos     INTEGER NOT NULL CHECK (quantidade_milesimos <> 0),
    tipo                     TEXT NOT NULL CHECK (tipo IN (
                                 'ENTRADA', 'VENDA', 'DEVOLUCAO', 'PERDA', 'AJUSTE', 'TRANSFERENCIA', 'ESTORNO')),
    origem_tipo              TEXT NOT NULL DEFAULT '',
    origem_id                TEXT NOT NULL DEFAULT '',
    motivo                   TEXT NOT NULL DEFAULT '',
    custo_unitario_centavos  INTEGER CHECK (custo_unitario_centavos IS NULL OR custo_unitario_centavos >= 0),
    criado_em                TEXT NOT NULL
);

CREATE INDEX ix_mov_estoque_produto ON movimentos_estoque (produto_id, criado_em);
CREATE INDEX ix_mov_estoque_origem ON movimentos_estoque (origem_tipo, origem_id);

CREATE TABLE entradas (
    id             TEXT PRIMARY KEY,
    fornecedor     TEXT NOT NULL,
    documento      TEXT NOT NULL,
    data_negocio   TEXT NOT NULL,
    frete_centavos INTEGER NOT NULL DEFAULT 0 CHECK (frete_centavos >= 0),
    criterio_rateio TEXT NOT NULL CHECK (criterio_rateio IN ('VALOR', 'QUANTIDADE')),
    operador_id    TEXT NOT NULL REFERENCES usuarios (id),
    criado_em      TEXT NOT NULL,
    UNIQUE (fornecedor, documento)
);

CREATE TABLE entradas_itens (
    id                      TEXT PRIMARY KEY,
    entrada_id              TEXT NOT NULL REFERENCES entradas (id),
    produto_id              TEXT NOT NULL REFERENCES produtos (id),
    quantidade_milesimos    INTEGER NOT NULL CHECK (quantidade_milesimos > 0),
    custo_unitario_centavos INTEGER NOT NULL CHECK (custo_unitario_centavos >= 0),
    frete_rateado_centavos  INTEGER NOT NULL DEFAULT 0 CHECK (frete_rateado_centavos >= 0)
);

CREATE INDEX ix_entradas_itens ON entradas_itens (entrada_id);

CREATE TABLE titulos (
    id                      TEXT PRIMARY KEY,
    venda_id                TEXT NOT NULL REFERENCES vendas (id),
    cliente_id              TEXT NOT NULL REFERENCES clientes (id),
    numero_parcela          INTEGER NOT NULL CHECK (numero_parcela > 0),
    total_parcelas          INTEGER NOT NULL CHECK (total_parcelas > 0),
    vencimento              TEXT NOT NULL,
    principal_centavos      INTEGER NOT NULL CHECK (principal_centavos >= 0),
    encargos_centavos       INTEGER NOT NULL DEFAULT 0 CHECK (encargos_centavos >= 0),
    status                  TEXT NOT NULL CHECK (status IN ('ABERTO', 'PARCIAL', 'PAGO', 'VENCIDO', 'CANCELADO')),
    criado_em               TEXT NOT NULL,
    UNIQUE (venda_id, numero_parcela),
    CHECK (numero_parcela <= total_parcelas)
);

CREATE INDEX ix_titulos_cliente ON titulos (cliente_id, status, vencimento);

CREATE TABLE recebimentos (
    id             TEXT PRIMARY KEY,
    titulo_id      TEXT NOT NULL REFERENCES titulos (id),
    data_negocio   TEXT NOT NULL,
    forma          TEXT NOT NULL CHECK (forma IN (
                       'DINHEIRO', 'PIX', 'DEBITO', 'CREDITO', 'TRANSFERENCIA', 'VALE', 'CHEQUE')),
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    turno_id       TEXT NOT NULL REFERENCES turnos (id),
    operador_id    TEXT NOT NULL REFERENCES usuarios (id),
    estorno        INTEGER NOT NULL DEFAULT 0 CHECK (estorno IN (0, 1)),
    referencia     TEXT NOT NULL DEFAULT '',
    criado_em      TEXT NOT NULL
);

CREATE INDEX ix_recebimentos_titulo ON recebimentos (titulo_id, estorno);

CREATE TABLE auditoria (
    sequencia     INTEGER PRIMARY KEY AUTOINCREMENT,
    id            TEXT NOT NULL UNIQUE,
    criado_em_utc TEXT NOT NULL,
    data_negocio  TEXT NOT NULL,
    ator_id       TEXT,
    acao          TEXT NOT NULL,
    entidade      TEXT NOT NULL DEFAULT '',
    entidade_id   TEXT NOT NULL DEFAULT '',
    antes         TEXT,
    depois        TEXT,
    motivo        TEXT NOT NULL DEFAULT '',
    autorizador_id TEXT,
    origem        TEXT NOT NULL DEFAULT 'DESKTOP',
    correlacao_id TEXT NOT NULL DEFAULT '',
    hash_anterior TEXT NOT NULL DEFAULT '',
    hash          TEXT NOT NULL
);

CREATE INDEX ix_auditoria_data ON auditoria (data_negocio, acao);
CREATE INDEX ix_auditoria_entidade ON auditoria (entidade, entidade_id);

-- Trilha append-only no próprio banco: UPDATE e DELETE são abortados.
CREATE TRIGGER tg_auditoria_sem_update
BEFORE UPDATE ON auditoria
BEGIN
    SELECT RAISE(ABORT, 'Trilha de auditoria é append-only: atualização proibida.');
END;

CREATE TRIGGER tg_auditoria_sem_delete
BEFORE DELETE ON auditoria
BEGIN
    SELECT RAISE(ABORT, 'Trilha de auditoria é append-only: exclusão proibida.');
END;

-- Idempotência da venda é garantida por vendas.chave_idempotencia (UNIQUE).
CREATE TABLE fechamentos (
    id            TEXT PRIMARY KEY,
    data_negocio  TEXT NOT NULL,
    turno_id      TEXT NOT NULL DEFAULT '',
    versao        INTEGER NOT NULL DEFAULT 1 CHECK (versao > 0),
    criado_em     TEXT NOT NULL,
    criado_por    TEXT REFERENCES usuarios (id),
    snapshot_json TEXT NOT NULL,
    UNIQUE (data_negocio, turno_id, versao)
);
