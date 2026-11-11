"""Área administrativa: diagnóstico, cópias de segurança, verificação e restauração."""

from __future__ import annotations

import shutil
import sqlite3

import pytest

from bussola_pdv.aplicacao.administracao import (
    ServicoAdministracao,
    StatusDiagnostico,
)
from bussola_pdv.dominio.erros import AutorizacaoNegada, ErroValidacao

pytestmark = pytest.mark.integracao


@pytest.fixture
def servico(cenario):
    return ServicoAdministracao(cenario.ctx)


class TestDiagnostico:
    def test_traz_ambiente_banco_e_conteudo(self, servico):
        itens = servico.diagnostico()
        nomes = {item.nome for item in itens}
        assert {"Python", "SQLite", "Integridade", "Admin Master ativo", "Argon2id"} <= nomes
        assert {item.grupo for item in itens} >= {"Aplicação", "Banco", "Conteúdo", "Segurança"}

    def test_base_saudavel_nao_tem_impedimento(self, servico):
        problemas = servico.problemas()
        assert problemas == [], [item.nome for item in problemas]

    def test_status_de_integridade_e_calculado(self, servico):
        integridade = next(item for item in servico.diagnostico() if item.nome == "Integridade")
        assert integridade.status is StatusDiagnostico.OK
        assert "quick_check" in integridade.detalhe

    def test_detecta_admin_master_ausente(self, cenario):
        cenario.ctx.conexao.execute(
            "UPDATE usuarios SET perfil = 'ADMIN' WHERE id = ?", (cenario.master.id,)
        )
        item = next(
            item
            for item in ServicoAdministracao(cenario.ctx).diagnostico()
            if item.nome == "Admin Master ativo"
        )
        assert item.status is StatusDiagnostico.ERRO
        assert "ninguém pode" in item.detalhe

    def test_pragmas_do_banco_sao_lidos(self, cenario):
        itens = {item.nome: item for item in ServicoAdministracao(cenario.ctx).diagnostico()}
        assert itens["Chaves estrangeiras"].valor == "ativas"
        assert itens["Sincronização"].valor == "FULL"

    def test_tamanho_da_base_nao_e_zero(self, servico):
        item = next(item for item in servico.diagnostico() if item.nome == "Tamanho da base")
        numero = float(item.valor.split()[0])
        assert numero > 0
        assert item.valor.split()[1] in {"B", "KB", "MB", "GB"}
        assert "WAL" in item.detalhe

    def test_formatar_bytes_escolhe_a_unidade(self):
        from bussola_pdv.aplicacao.administracao import formatar_bytes

        assert formatar_bytes(512) == "512 B"
        assert formatar_bytes(2048) == "2 KB"
        assert formatar_bytes(5 * 1024 * 1024) == "5.0 MB"
        assert formatar_bytes(3 * 1024**3) == "3.0 GB"

    def test_versao_do_esquema_aparece(self, servico):
        esquema = next(item for item in servico.diagnostico() if item.nome == "Esquema")
        assert esquema.valor.startswith("v3 de v3")
        assert esquema.status is StatusDiagnostico.OK


class TestManutencao:
    def test_verificacao_exige_permissao(self, servico, cenario):
        with pytest.raises(AutorizacaoNegada):
            servico.verificar_integridade(cenario.operador)

    def test_verificacao_completa(self, servico, cenario):
        resultado = servico.verificar_integridade(cenario.admin)
        assert resultado["integro"] is True
        assert resultado["auditoria_integra"] is True
        assert resultado["eventos_auditoria"] > 0

    def test_otimizar_registra_evento(self, servico, cenario):
        resultado = servico.otimizar(cenario.admin)
        assert resultado["liberado_bytes"] >= 0
        assert cenario.ctx.auditoria.listar(limite=3)[0].acao.value == "MANUTENCAO_EXECUTADA"

    def test_otimizar_exige_permissao(self, servico, cenario):
        with pytest.raises(AutorizacaoNegada):
            servico.otimizar(cenario.gerente)


class TestBackup:
    def test_copia_e_verificada(self, servico, cenario, tmp_path):
        resultado = servico.backup(cenario.admin, tmp_path / "copias")
        assert resultado["verificado"] is True
        caminho = resultado["arquivo"]
        assert caminho.endswith(".db")
        assert cenario.ctx.auditoria.listar(limite=3)[0].acao.value == "BACKUP_EXECUTADO"

    def test_copia_exige_permissao(self, servico, cenario, tmp_path):
        with pytest.raises(AutorizacaoNegada):
            servico.backup(cenario.operador, tmp_path)

    def test_copia_contem_os_dados(self, servico, cenario, tmp_path):
        resultado = servico.backup(cenario.admin, tmp_path)
        conexao = sqlite3.connect(str(resultado["arquivo"]))
        try:
            usuarios = conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
            versao = conexao.execute("SELECT MAX(versao) FROM esquema_versao").fetchone()[0]
        finally:
            conexao.close()
        assert usuarios >= 5
        assert versao == 3

    def test_verificacao_do_arquivo_aponta_tabelas_faltando(self, servico, cenario, tmp_path):
        alvo = tmp_path / "incompleto.db"
        conexao = sqlite3.connect(alvo)
        conexao.execute("CREATE TABLE qualquer_coisa (id TEXT)")
        conexao.commit()
        conexao.close()
        resultado = servico.verificar_arquivo(alvo)
        assert resultado["integro"] is False
        assert "usuarios" in resultado["faltando"]

    def test_arquivo_corrompido_e_recusado(self, servico, tmp_path):
        ruim = tmp_path / "ruim.db"
        ruim.write_bytes(b"isto nao e um banco sqlite")
        with pytest.raises(ErroValidacao):
            servico.verificar_arquivo(ruim)

    def test_lista_de_copias_ordenada(self, servico, cenario, tmp_path):
        servico.backup(cenario.admin, tmp_path)
        copias = servico.listar_copias(tmp_path)
        assert copias
        assert copias[0]["arquivo"].endswith(".db")
        assert servico.listar_copias(tmp_path / "inexistente") == []


class TestRestauracao:
    def test_restaurar_exige_master(self, servico, cenario, tmp_path):
        copia = servico.backup(cenario.admin, tmp_path)["arquivo"]
        with pytest.raises(AutorizacaoNegada):
            servico.restaurar(cenario.admin, copia)
        with pytest.raises(AutorizacaoNegada):
            servico.restaurar(cenario.operador, copia)

    def test_restaurar_devolve_estado_anterior(self, servico, cenario, tmp_path):
        copia = servico.backup(cenario.admin, tmp_path)["arquivo"]
        produtos_antes = cenario.ctx.conexao.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]

        from bussola_pdv.aplicacao.estoque import ServicoEstoque

        ServicoEstoque(cenario.ctx).criar_produto(
            operador=cenario.admin, codigo="ZZZ", descricao="Produto criado depois",
            preco=100, custo=50, categoria="Teste", unidade="UN",
        )
        assert cenario.ctx.conexao.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == (
            produtos_antes + 1
        )

        resultado = servico.restaurar(cenario.master, copia)
        assert resultado["integro"] is True
        assert cenario.ctx.conexao.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == (
            produtos_antes
        )
        assert ".antes-de-restaurar-" in resultado["copia_de_seguranca"]
        assert cenario.ctx.auditoria.listar(limite=3)[0].acao.value == "BACKUP_RESTAURADO"

    def test_copia_da_base_anterior_fica_ao_lado(self, servico, cenario, tmp_path):
        copia = servico.backup(cenario.admin, tmp_path)["arquivo"]
        resultado = servico.restaurar(cenario.master, copia)
        caminho = resultado["copia_de_seguranca"]
        assert ".antes-de-restaurar-" in caminho
        from pathlib import Path

        assert Path(caminho).exists()

    def test_copia_invalida_nao_e_restaurada(self, servico, cenario, tmp_path):
        ruim = tmp_path / "ruim.db"
        ruim.write_bytes(b"lixo")
        with pytest.raises(ErroValidacao):
            servico.restaurar(cenario.master, ruim)

    def test_nao_restaura_base_de_versao_futura(self, servico, cenario, tmp_path):
        copia = servico.backup(cenario.admin, tmp_path)["arquivo"]
        conexao = sqlite3.connect(copia)
        conexao.execute(
            "INSERT INTO esquema_versao (versao, descricao, aplicado_em) VALUES (99, 'futuro', '2030-01-01')"
        )
        conexao.commit()
        conexao.close()
        with pytest.raises(ErroValidacao):
            servico.restaurar(cenario.master, copia)
        shutil.rmtree(tmp_path, ignore_errors=True)
