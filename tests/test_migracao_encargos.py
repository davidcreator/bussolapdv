"""Migração 0005: encargos cobrados e o novo tipo de movimento no caixa.

A migração reconstrói `movimentos_caixa` (o SQLite não altera CHECK no lugar).
Este teste prova as duas coisas que podem dar errado numa reconstrução:
os movimentos antigos **continuam lá** e a tabela nova aceita o tipo novo.
"""

from __future__ import annotations

import pytest

from bussola_pdv.infra.sqlite.conexao import abrir_conexao
from bussola_pdv.infra.sqlite.migrador import migrar, versao_atual

pytestmark = pytest.mark.integracao


def test_migracao_preserva_movimentos_e_aceita_encargos(tmp_path):
    conexao = abrir_conexao(tmp_path / "m.db")
    migrar(conexao, ate=4)
    assert versao_atual(conexao) == 4

    agora = "2026-11-19T12:00:00+00:00"
    conexao.execute(
        "INSERT INTO usuarios (id, login, nome, perfil, senha_hash, ativo, tentativas_falhas,"
        " criado_em, criado_por) VALUES ('u1', 'ana', 'Ana', 'ADMIN_MASTER', 'x', 1, 0, ?, 'u1')",
        (agora,),
    )
    conexao.execute(
        "INSERT INTO caixas (id, nome, ativo, criado_em) VALUES ('c1', 'Caixa 1', 1, ?)",
        (agora,),
    )
    conexao.execute(
        "INSERT INTO turnos (id, caixa_id, operador_id, data_negocio, fundo_centavos,"
        " aberto_em, status) VALUES ('t1', 'c1', 'u1', '2026-11-19', 10000, ?, 'ABERTO')",
        (agora,),
    )
    conexao.execute(
        "INSERT INTO movimentos_caixa (id, turno_id, tipo, valor_centavos, motivo, criado_em)"
        " VALUES ('m1', 't1', 'VENDA_DINHEIRO', 5000, 'venda', ?)",
        (agora,),
    )
    conexao.commit()

    # da 4 em diante o que roda é [5, 6, …]; o teste só exige 5 na lista
    assert 5 in migrar(conexao)

    # o movimento antigo sobreviveu à reconstrução da tabela
    linha = conexao.execute("SELECT tipo, valor_centavos FROM movimentos_caixa").fetchone()
    assert (linha["tipo"], linha["valor_centavos"]) == ("VENDA_DINHEIRO", 5000)

    # e o tipo novo passou a ser aceito
    conexao.execute(
        "INSERT INTO movimentos_caixa (id, turno_id, tipo, valor_centavos, motivo, criado_em)"
        " VALUES ('m2', 't1', 'RECEBIMENTO_ENCARGOS', 300, 'encargos', ?)",
        (agora,),
    )
    assert conexao.execute("SELECT COUNT(*) FROM movimentos_caixa").fetchone()[0] == 2
    with pytest.raises(Exception, match="CHECK"):
        conexao.execute(
            "INSERT INTO movimentos_caixa (id, turno_id, tipo, valor_centavos, motivo, criado_em)"
            " VALUES ('m3', 't1', 'TIPO_INVENTADO', 100, '', ?)",
            (agora,),
        )
    conexao.close()


def test_recebimentos_ganham_as_colunas_de_encargo(tmp_path):
    conexao = abrir_conexao(tmp_path / "m2.db")
    migrar(conexao)
    colunas = {
        linha["name"] for linha in conexao.execute("PRAGMA table_info(recebimentos)").fetchall()
    }
    assert {"multa_centavos", "juros_centavos", "encargo_centavos", "dias_atraso"} <= colunas
    assert "encargos_dispensados" in colunas
    conexao.close()
