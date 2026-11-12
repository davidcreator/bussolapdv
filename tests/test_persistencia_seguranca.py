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


def sem_base_iana():
    """Simula o Windows sem `tzdata`: todo `ZoneInfo(nome)` estoura."""
    from zoneinfo import ZoneInfoNotFoundError

    def _explodir(*_args, **_kwargs):
        raise ZoneInfoNotFoundError("No time zone found with key America/Sao_Paulo")

    return _explodir


class TestFusoNoWindowsSemTzdata:
    """O `ZoneInfoNotFoundError` do Windows sem `tzdata` não pode derrubar o PDV.

    Relato de campo (v0.6.0, Python 3.14 do Windows): o primeiro uso morria em
    `ZoneInfo("America/Sao_Paulo")` — o Windows não traz base IANA, ela só existe
    no pacote `tzdata`. O programa agora segue com deslocamento fixo e registra o
    aviso, em vez de impedir a loja de abrir.
    """

    def test_fuso_cai_para_deslocamento_fixo_sem_base_iana(self, monkeypatch):
        from zoneinfo import ZoneInfoNotFoundError

        from bussola_pdv.dominio import relogio as modulo

        def sem_base(*_args, **_kwargs):
            raise ZoneInfoNotFoundError("No time zone found with key America/Sao_Paulo")

        modulo.limpar_avisos_de_fuso()
        monkeypatch.setattr(modulo, "ZoneInfo", sem_base)

        fuso = modulo.resolver_fuso("America/Sao_Paulo")
        assert fuso.utcoffset(datetime(2026, 11, 11, 12, tzinfo=UTC)).total_seconds() == -3 * 3600
        avisos = modulo.avisos_de_fuso()
        assert len(avisos) == 1
        assert "tzdata" in avisos[0]
        assert "UTC-03:00" in avisos[0]

    def test_relogio_do_sistema_data_a_loja_com_o_fuso_de_reserva(self, monkeypatch):

        from bussola_pdv.dominio import relogio as modulo

        monkeypatch.setattr(modulo, "ZoneInfo", sem_base_iana())
        relogio = modulo.RelogioSistema()
        assert relogio.data_negocio() == relogio.hoje().date().isoformat()
        assert relogio.hoje().utcoffset().total_seconds() == -3 * 3600

    def test_fuso_desconhecido_aponta_o_pacote(self, monkeypatch):

        from bussola_pdv.dominio import relogio as modulo

        monkeypatch.setattr(modulo, "ZoneInfo", sem_base_iana())
        with pytest.raises(ValueError, match="tzdata"):
            modulo.resolver_fuso("Marte/Olympus")

    def test_formatar_local_usa_o_mesmo_fuso(self, monkeypatch):

        from bussola_pdv.dominio import relogio as modulo

        monkeypatch.setattr(modulo, "ZoneInfo", sem_base_iana())
        # 15:00 UTC = 12:00 em São Paulo (UTC-3)
        assert modulo.formatar_local(datetime(2026, 11, 11, 15, tzinfo=UTC)) == "11/11/2026 12:00"

    def test_contexto_nao_abre_o_arquivo_quando_o_fuso_falha(self, monkeypatch):
        """Ordem importa: fuso primeiro, arquivo depois — senão a base fica presa.

        Era exatamente isso que virava `WinError 32` na tela: a exceção do fuso
        nascia com o SQLite já aberto e o programa tentava renomear a base.
        """
        from zoneinfo import ZoneInfoNotFoundError

        from bussola_pdv.aplicacao import contexto as modulo_contexto

        def explodir_fuso(*_args, **_kwargs):
            raise ZoneInfoNotFoundError("America/Sao_Paulo")

        def nao_deveria_abrir(*_args, **_kwargs):
            raise AssertionError("a conexão não pode ser aberta antes do relógio")

        monkeypatch.setattr(modulo_contexto, "RelogioSistema", explodir_fuso)
        monkeypatch.setattr(modulo_contexto, "abrir_conexao", nao_deveria_abrir)
        with pytest.raises(ZoneInfoNotFoundError):
            modulo_contexto.Contexto.abrir("nao-chega-a-existir.db")

    def test_cli_relogio_diagnostica_o_fuso_sem_base(self, capsys):
        """`bussola relogio` responde a pergunta do suporte sem precisar de banco."""
        from bussola_pdv.cli import main as cli_main

        assert cli_main(["relogio"]) == 0
        saida = capsys.readouterr().out
        assert "Fuso configurado: America/Sao_Paulo" in saida
        assert "Fuso em uso:" in saida
        assert "Data de negócio:" in saida
        assert ("Base IANA de fusos: OK" in saida) or ("tzdata" in saida)

    def test_cli_relogio_com_banco_mostra_a_data_de_negocio(self, tmp_path, capsys):
        from bussola_pdv.aplicacao.contexto import Contexto
        from bussola_pdv.cli import main as cli_main
        from bussola_pdv.dominio.relogio import limpar_avisos_de_fuso

        limpar_avisos_de_fuso()
        banco = tmp_path / "com_base.db"
        Contexto.abrir(banco).fechar()

        assert cli_main(["relogio", "--banco", str(banco)]) == 0
        saida = capsys.readouterr().out
        assert "Data de negócio atual: " in saida
        assert saida.splitlines()[0].count("-") == 2  # data ISO AAAA-MM-DD

    def test_conexao_e_fechada_quando_a_migracao_falha(self, monkeypatch, tmp_path):
        from bussola_pdv.aplicacao import contexto as modulo_contexto

        def migracao_quebrada(_conexao):
            raise RuntimeError("migração interrompida")

        monkeypatch.setattr(modulo_contexto, "migrar", migracao_quebrada)
        with pytest.raises(RuntimeError):
            modulo_contexto.Contexto.abrir(tmp_path / "pdv.db")
        # se a conexão tivesse ficado aberta, o arquivo continuaria com o journal
        assert list(tmp_path.glob("pdv.db-journal")) == []
