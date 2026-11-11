"""Migração 0003: reconstrução de `usuarios` sem perder dados nem integridade.

Este é o teste mais delicado do conjunto: a migração troca o CHECK de perfis, e
para isso precisa recriar a tabela que é referenciada por oito chaves
estrangeiras (vendas, turnos, pagamentos, auditoria, títulos...).
"""

from __future__ import annotations

import sqlite3

import pytest

from bussola_pdv.infra.sqlite.conexao import abrir_conexao
from bussola_pdv.infra.sqlite.migrador import migrar, versao_atual

pytestmark = pytest.mark.integracao

HASH_FALSO = "$argon2id$v=19$m=65536,t=3,p=4$abcdef$0123456789abcdef"


def _db_v2(tmp_path, com_movimento: bool = True):
    """Banco parado na versão 2, como estava antes desta entrega."""
    caminho = tmp_path / "legado.db"
    conexao = abrir_conexao(caminho)
    migrar(conexao, ate=2)
    assert versao_atual(conexao) == 2
    with conexao:
        legados = [
            ("u1", "ana.operadora", "Ana Operadora", "OPERADOR"),
            ("u2", "bruno.admin", "Bruno Admin", "ADMINISTRADOR"),
            ("u3", "carla.gerente", "Carla Gerente", "GERENTE"),
        ]
        for identificador, login, nome, perfil in legados:
            conexao.execute(
                """INSERT INTO usuarios (id, login, nome, perfil, senha_hash, ativo,
                                         criado_em)
                   VALUES (?, ?, ?, ?, ?, 1, '2026-01-10T12:00:00+00:00')""",
                (identificador, login, nome, perfil, HASH_FALSO),
            )
        conexao.execute(
            """INSERT INTO caixas (id, nome, ativo, criado_em)
               VALUES ('cx1', 'Caixa 1', 1, '2026-01-10T12:00:00+00:00')"""
        )
        if com_movimento:
            conexao.execute(
                """INSERT INTO turnos (id, caixa_id, operador_id, fundo_centavos, aberto_em,
                                       data_negocio, status)
                   VALUES ('t1', 'cx1', 'u1', 10000, '2026-01-10T13:00:00+00:00',
                           '2026-01-10', 'ABERTO')"""
            )
            conexao.execute(
                """INSERT INTO vendas (id, numero, serie, data_negocio, criado_em, status,
                                       operador_id, turno_id, subtotal_centavos,
                                       desconto_centavos, acrescimo_centavos, total_centavos,
                                       custo_total_centavos, chave_idempotencia)
                   VALUES ('v1', 1, 'A', '2026-01-10', '2026-01-10T13:10:00+00:00', 'CONCLUIDA',
                           'u1', 't1', 1000, 0, 0, 1000, 500, 'chave-legada')"""
            )
    return conexao


def test_migracao_converte_perfis_legados(tmp_path):
    conexao = _db_v2(tmp_path)
    aplicadas = migrar(conexao)
    assert aplicadas == [3]
    perfis = {
        linha["login"]: linha["perfil"]
        for linha in conexao.execute("SELECT login, perfil FROM usuarios")
    }
    assert perfis == {
        "ana.operadora": "ATENDENTE",
        "bruno.admin": "ADMIN",
        "carla.gerente": "GERENTE",
    }
    conexao.close()


def test_migracao_preserva_ids_hashes_e_datas(tmp_path):
    conexao = _db_v2(tmp_path)
    migrar(conexao)
    linha = conexao.execute("SELECT * FROM usuarios WHERE login = 'ana.operadora'").fetchone()
    assert linha["id"] == "u1"
    assert linha["senha_hash"] == HASH_FALSO
    assert linha["criado_em"] == "2026-01-10T12:00:00+00:00"
    assert linha["criado_por"] is None
    conexao.close()


def test_migracao_nao_deixa_referencia_orfa(tmp_path):
    conexao = _db_v2(tmp_path)
    migrar(conexao)
    assert conexao.execute("PRAGMA foreign_key_check").fetchall() == []
    venda = conexao.execute("SELECT operador_id FROM vendas WHERE id = 'v1'").fetchone()
    assert venda["operador_id"] == "u1"
    turno = conexao.execute("SELECT operador_id FROM turnos WHERE id = 't1'").fetchone()
    assert turno["operador_id"] == "u1"
    assert conexao.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conexao.close()


def test_migracao_recria_travas_e_indices(tmp_path):
    conexao = _db_v2(tmp_path)
    migrar(conexao)
    nomes = {
        linha[0]
        for linha in conexao.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('index','trigger')"
        )
    }
    assert {"ux_usuarios_master_unico", "tg_usuarios_sem_delete", "ix_usuarios_perfil"} <= nomes
    tabelas = {
        linha[0] for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "permissoes_perfil" in tabelas
    assert "usuarios_novo" not in tabelas  # tabela temporária não pode sobrar
    conexao.close()


def test_check_novo_aceita_cinco_perfis_e_recusa_inventado(tmp_path):
    conexao = _db_v2(tmp_path)
    migrar(conexao)
    for perfil in ("ATENDENTE", "GERENTE", "CONTABILIDADE", "ADMIN", "ADMIN_MASTER"):
        conexao.execute(
            """INSERT INTO usuarios (id, login, nome, perfil, senha_hash, ativo, criado_em)
               VALUES (?, ?, ?, ?, ?, 1, '2026-11-11')""",
            (f"id-{perfil}", f"login.{perfil.lower()}", perfil, perfil, HASH_FALSO),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute(
            """INSERT INTO usuarios (id, login, nome, perfil, senha_hash, ativo, criado_em)
               VALUES ('x', 'login.invalido', 'X', 'ROOT', ?, 1, '2026-11-11')""",
            (HASH_FALSO,),
        )
    conexao.close()


def test_base_vazia_tambem_migra(tmp_path):
    conexao = abrir_conexao(tmp_path / "vazio.db")
    assert migrar(conexao) == [1, 2, 3]
    assert conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0
    conexao.close()


def test_migracao_e_idempotente(tmp_path):
    conexao = _db_v2(tmp_path)
    migrar(conexao)
    assert migrar(conexao) == []
    assert versao_atual(conexao) == 3
    conexao.close()
