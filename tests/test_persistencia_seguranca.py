"""Migrações, PRAGMAs, ausência de float e hash de senha."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from bussola_pdv.aplicacao.autenticacao import ServicoAutenticacao
from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.dominio.erros import CredenciaisInvalidas, ErroValidacao, UsuarioBloqueado
from bussola_pdv.dominio.relogio import RelogioFixo
from bussola_pdv.dominio.seguranca import (
    PoliticaBloqueio,
    gerar_hash,
    precisa_rehash,
    validar_pin,
    validar_senha,
    verificar_senha,
)
from bussola_pdv.dominio.usuario import Acao, Perfil, Usuario, exigir_autorizacao
from bussola_pdv.infra.sqlite.conexao import abrir_conexao, fazer_backup, verificar_integridade
from bussola_pdv.infra.sqlite.migrador import ErroMigracao, migrar, versao_atual

pytestmark = pytest.mark.integracao


class TestMigracoes:
    def test_aplica_todas_as_versoes(self, tmp_path):
        conn = abrir_conexao(tmp_path / "m.db")
        aplicadas = migrar(conn)
        assert aplicadas == [1, 2, 3]
        assert versao_atual(conn) == 3
        conn.close()

    def test_migrar_duas_vezes_nao_repete(self, tmp_path):
        conn = abrir_conexao(tmp_path / "m.db")
        migrar(conn)
        assert migrar(conn) == []
        conn.close()

    def test_pragmas_essenciais(self, tmp_path):
        conn = abrir_conexao(tmp_path / "p.db")
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL
        conn.close()

    def test_chave_estrangeira_e_aplicada(self, tmp_path):
        conn = abrir_conexao(tmp_path / "fk.db")
        migrar(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO vendas (id, numero, data_negocio, criado_em, operador_id, turno_id,"
                " status, subtotal_centavos, desconto_centavos, acrescimo_centavos,"
                " total_centavos, custo_total_centavos, chave_idempotencia)"
                " VALUES ('v1', 1, '2026-11-11', '2026-11-11T00:00:00+00:00', 'inexistente',"
                " 'inexistente', 'CONCLUIDA', 0, 0, 0, 0, 0, 'k1')"
            )
        conn.close()

    def test_nenhuma_coluna_monetaria_e_real(self, tmp_path):
        contexto = Contexto.abrir(tmp_path / "tipos.db")
        colunas_reais = []
        tabelas = [
            linha[0]
            for linha in contexto.conexao.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for tabela in tabelas:
            for coluna in contexto.conexao.execute(f"PRAGMA table_info({tabela})"):
                if coluna["type"].upper() == "REAL":
                    colunas_reais.append(f"{tabela}.{coluna['name']}")
        contexto.fechar()
        assert colunas_reais == []

    def test_migracao_invalida_nao_deixa_estado_parcial(self, tmp_path):
        diretorio = tmp_path / "migracoes"
        diretorio.mkdir()
        (diretorio / "0001_quebrada.sql").write_text(
            "CREATE TABLE ok (id INTEGER);\nCREATE TABLE ok (id INTEGER);\n", encoding="utf-8"
        )
        conn = abrir_conexao(tmp_path / "falha.db")
        with pytest.raises(ErroMigracao):
            migrar(conn, diretorio=diretorio)
        # Nenhuma tabela criada e nenhuma versão registrada: transação revertida.
        tabelas = [linha[0] for linha in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "ok" not in tabelas
        assert versao_atual(conn) == 0
        conn.close()


class TestBackup:
    def test_backup_e_restauracao_isolada(self, cenario, tmp_path):
        from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
        from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_dinheiro
        from bussola_pdv.dominio.venda import Carrinho

        carrinho = Carrinho()
        carrinho.adicionar(cenario.produto_a, "1")
        total = carrinho.totais().total
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=PlanoPagamento.de_pagamentos(pagamento_dinheiro(total)),
            )
        )

        destino = tmp_path / "copias" / "backup.db"
        caminho = fazer_backup(cenario.ctx.conexao, destino)
        assert caminho.exists()

        restaurado = Contexto.abrir(caminho)
        assert restaurado.vendas.listar(limite=10)[0]["total_centavos"] == total.centavos
        assert restaurado.auditoria.verificar().integro
        integro, problemas = verificar_integridade(restaurado.conexao)
        assert integro, problemas
        restaurado.fechar()

    def test_banco_original_nao_e_alterado_pelo_backup(self, cenario, tmp_path):
        antes = cenario.ctx.conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        fazer_backup(cenario.ctx.conexao, tmp_path / "copia.db")
        depois = cenario.ctx.conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        assert antes == depois


class TestSeguranca:
    def test_hash_nao_guarda_senha_em_texto(self):
        hash_ = gerar_hash("senha-forte-123")
        assert "senha-forte-123" not in hash_
        assert hash_.startswith("$argon2id$")
        assert verificar_senha("senha-forte-123", hash_)
        assert not verificar_senha("senha-forte-124", hash_)

    def test_hashes_diferentes_para_mesma_senha(self):
        assert gerar_hash("senha-forte-123") != gerar_hash("senha-forte-123")

    def test_hash_atual_nao_precisa_rehash(self):
        assert not precisa_rehash(gerar_hash("senha-forte-123"))

    @pytest.mark.parametrize("senha", ["curta", "aaaaaaaa"])
    def test_politica_de_senha(self, senha):
        with pytest.raises(ErroValidacao):
            validar_senha(senha)

    @pytest.mark.parametrize("pin", ["123", "123456789", "12a4"])
    def test_politica_de_pin(self, pin):
        with pytest.raises(ErroValidacao):
            validar_pin(pin)

    def test_pin_valido(self):
        validar_pin("1234")

    def test_bloqueio_apos_tentativas(self, ctx, hash_senha):
        servico = ServicoAutenticacao(ctx)
        usuario = Usuario(login="op", nome="Op", perfil=Perfil.OPERADOR, senha_hash=hash_senha)
        with ctx.em_transacao():
            ctx.usuarios.criar(usuario, criado_em=ctx.agora().isoformat())
        for _ in range(5):
            with pytest.raises(CredenciaisInvalidas):
                servico.entrar("op", "senha-errada")
        with pytest.raises(UsuarioBloqueado):
            servico.entrar("op", "senha-de-teste")

    def test_login_sucesso_limpa_tentativas(self, ctx, hash_senha):
        servico = ServicoAutenticacao(ctx)
        usuario = Usuario(login="op2", nome="Op", perfil=Perfil.OPERADOR, senha_hash=hash_senha)
        with ctx.em_transacao():
            ctx.usuarios.criar(usuario, criado_em=ctx.agora().isoformat())
        with pytest.raises(CredenciaisInvalidas):
            servico.entrar("op2", "errada")
        resultado = servico.entrar("op2", "senha-de-teste")
        assert resultado.usuario.login == "op2"
        assert ctx.usuarios.por_login("op2").tentativas_falhas == 0

    def test_login_inexistente_usa_mesma_mensagem(self, ctx):
        servico = ServicoAutenticacao(ctx)
        with pytest.raises(CredenciaisInvalidas) as erro:
            servico.entrar("fantasma", "qualquer-senha")
        assert "Login ou senha inválidos" in str(erro.value)

    def test_bloqueio_expira(self):
        agora = datetime(2026, 11, 11, 12, tzinfo=UTC)
        politica = PoliticaBloqueio(maximo_tentativas=3, duracao_bloqueio=timedelta(minutes=5))
        bloqueado = politica.bloqueado_ate(agora, 3)
        assert bloqueado == agora + timedelta(minutes=5)
        politica.conferir(agora + timedelta(minutes=6), bloqueado)
        with pytest.raises(UsuarioBloqueado):
            politica.conferir(agora + timedelta(minutes=1), bloqueado)


class TestPermissoes:
    def test_operador_nao_cancela(self):
        operador = Usuario(login="o", nome="O", perfil=Perfil.OPERADOR, senha_hash="x")
        from bussola_pdv.dominio.erros import AutorizacaoNegada

        with pytest.raises(AutorizacaoNegada):
            operador.exigir(Acao.VENDA_CANCELAR)

    def test_autorizador_precisa_ter_permissao(self):
        operador = Usuario(login="o", nome="O", perfil=Perfil.OPERADOR, senha_hash="x")
        gerente = Usuario(login="g", nome="G", perfil=Perfil.GERENTE, senha_hash="x")
        exigir_autorizacao(operador, Acao.PDV_DESCONTO_EXCEPCIONAL, gerente)
        from bussola_pdv.dominio.erros import AutorizacaoNegada

        with pytest.raises(AutorizacaoNegada):
            exigir_autorizacao(operador, Acao.PDV_DESCONTO_EXCEPCIONAL, operador)

    def test_usuario_inativo_nao_autoriza(self):
        from bussola_pdv.dominio.erros import AutorizacaoNegada

        inativo = Usuario(
            login="g", nome="G", perfil=Perfil.GERENTE, senha_hash="x", ativo=False
        )
        with pytest.raises(AutorizacaoNegada):
            inativo.exigir(Acao.PDV_DESCONTO_EXCEPCIONAL)


class TestRelogio:
    def test_relogio_fixo_e_utc(self):
        relogio = RelogioFixo(datetime(2026, 11, 11, 3, tzinfo=UTC))
        assert relogio.data_negocio() == "2026-11-11"
        assert relogio.agora_utc().tzinfo is not None
        relogio.avancar(days=1)
        assert relogio.data_negocio() == "2026-11-12"

    def test_relogio_ingenuo_e_recusado(self):
        with pytest.raises(ValueError):
            RelogioFixo(datetime(2026, 11, 11))
