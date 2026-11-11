-- sem-foreign-keys
-- Migração 0003 — hierarquia de cinco perfis, permissões configuráveis e marca.
--
-- A tabela `usuarios` precisa ser reconstruída porque a versão 1 trazia um CHECK
-- com apenas três perfis, e SQLite não permite alterar CHECK. A reconstrução
-- acontece com `foreign_keys=OFF` (diretiva lida pelo migrador) e é verificada
-- com `PRAGMA foreign_key_check` antes do COMMIT.
--
-- Mapeamento dos perfis anteriores:
--   OPERADOR        -> ATENDENTE
--   ADMINISTRADOR   -> ADMIN
--   GERENTE         -> GERENTE

CREATE TABLE usuarios_novo (
    id                TEXT PRIMARY KEY,
    login             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nome              TEXT NOT NULL,
    perfil            TEXT NOT NULL CHECK (
                          perfil IN ('ATENDENTE', 'GERENTE', 'CONTABILIDADE', 'ADMIN', 'ADMIN_MASTER')
                      ),
    senha_hash        TEXT NOT NULL,
    ativo             INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    tentativas_falhas INTEGER NOT NULL DEFAULT 0 CHECK (tentativas_falhas >= 0),
    bloqueado_ate     TEXT,
    criado_em         TEXT NOT NULL,
    criado_por        TEXT REFERENCES usuarios (id)
);

INSERT INTO usuarios_novo (
    id, login, nome, perfil, senha_hash, ativo, tentativas_falhas, bloqueado_ate, criado_em, criado_por
)
SELECT id, login, nome,
       CASE perfil
           WHEN 'OPERADOR' THEN 'ATENDENTE'
           WHEN 'ADMINISTRADOR' THEN 'ADMIN'
           ELSE perfil
       END,
       senha_hash, ativo, tentativas_falhas, bloqueado_ate, criado_em, NULL
FROM usuarios;

DROP TABLE usuarios;

ALTER TABLE usuarios_novo RENAME TO usuarios;

CREATE INDEX IF NOT EXISTS ix_usuarios_perfil ON usuarios (perfil, ativo);

-- Um único Admin Master ativo por instalação: o proprietário é sempre identificável.
CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_master_unico
    ON usuarios (perfil) WHERE perfil = 'ADMIN_MASTER' AND ativo = 1;

-- Histórico de quem operou não pode desaparecer: desativa-se, não se exclui.
CREATE TRIGGER tg_usuarios_sem_delete
BEFORE DELETE ON usuarios BEGIN
    SELECT RAISE(ABORT, 'Usuários não podem ser excluídos; desative o acesso.');
END;

-- Matriz de permissões por perfil, editável apenas pelo Admin Master.
-- A ausência de linha significa "usa o padrão do código" (usuarios.PERMISSOES_PADRAO).
CREATE TABLE permissoes_perfil (
    perfil         TEXT NOT NULL CHECK (
                       perfil IN ('ATENDENTE', 'GERENTE', 'CONTABILIDADE', 'ADMIN', 'ADMIN_MASTER')
                   ),
    acao           TEXT NOT NULL,
    permitido      INTEGER NOT NULL CHECK (permitido IN (0, 1)),
    atualizado_em  TEXT NOT NULL,
    atualizado_por TEXT REFERENCES usuarios (id),
    PRIMARY KEY (perfil, acao)
);

CREATE INDEX IF NOT EXISTS ix_permissoes_perfil_acao ON permissoes_perfil (acao);
