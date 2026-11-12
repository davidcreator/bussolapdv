"""Ajuda, guia de uso e mentor: conteúdo coerente com as telas e preferência que gruda.

O teste que mais importa aqui é o de **alvo do passo**: o mentor destaca o campo pelo
nome do atributo do widget. Se alguém renomear `campo_codigo` no PDV e esquecer o
guia, o operador fica com um passo que aponta para o nada. Estes testes amarram os
dois lados (texto do guia ↔ widget real) para o erro aparecer na suíte, não na loja.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from bussola_pdv.aplicacao import ajuda as mod_ajuda
from bussola_pdv.aplicacao.ajuda import (
    CHAVE_GUIADO,
    CHAVE_VERSAO,
    GUIA,
    POR_CHAVE,
    TEMA_DO_MODULO,
    VERSAO_GUIA,
    ServicoAjuda,
    buscar,
    guia_em_markdown,
    tema_em_html,
)
from bussola_pdv.ui.ajuda import JanelaAjuda
from bussola_pdv.ui.icones import DESENHOS
from bussola_pdv.ui.janela import DETALHES_MODULO, MODULO_ADMIN, MODULO_AJUDA, MODULOS
from bussola_pdv.ui.mentor import PainelMentor, alvos_da_tela


@pytest.fixture
def app():
    return QApplication.instance() or QApplication(["teste-ajuda"])


# Telas reais usadas pelo mentor, por módulo da janela principal.
def _telas(cenario) -> dict[str, QWidget]:
    from bussola_pdv.ui.tela_caixa import TelaCaixa
    from bussola_pdv.ui.tela_pdv import TelaPDV
    from bussola_pdv.ui.telas_clientes import TelaClientes
    from bussola_pdv.ui.telas_consulta import (
        TelaAuditoria,
        TelaFechamento,
        TelaProdutos,
        TelaVendas,
    )
    from bussola_pdv.ui.telas_crediario import TelaCrediario
    from bussola_pdv.ui.telas_estoque import TelaEstoque

    ctx, usuario = cenario.ctx, cenario.gerente
    return {
        "PDV": TelaPDV(ctx, usuario),
        "Caixa": TelaCaixa(ctx, usuario),
        "Produtos": TelaProdutos(ctx, usuario),
        "Vendas": TelaVendas(ctx, usuario),
        "Fechamento": TelaFechamento(ctx, usuario),
        "Auditoria": TelaAuditoria(ctx, usuario),
        "Clientes": TelaClientes(ctx, usuario),
        "Crediário": TelaCrediario(ctx, usuario),
        "Estoque": TelaEstoque(ctx, usuario),
    }


class TestConteudoDoGuia:
    def test_todo_tema_tem_o_minimo_para_ensinar(self):
        # Temas de tela conduzem passo a passo; temas de referência (mensagens de erro,
        # atalhos) explicam por tabela. Todo tema, porém, tem que ensinar *algo*.
        for tema in GUIA:
            assert tema.titulo, tema.chave
            assert tema.resumo, tema.chave
            assert tema.passos or tema.campos or tema.atalhos, f"{tema.chave} não ensina nada"
            for passo in tema.passos:
                assert passo.titulo, tema.chave
                assert passo.texto, tema.chave
            if tema.modulo:  # tema de tela é o que o mentor conduz: precisa de passos
                assert tema.passos, f"{tema.chave} é tema de tela sem passos"
            for relacionado in tema.relacionados:
                assert relacionado in POR_CHAVE, f"{tema.chave} aponta para tema inexistente"

    def test_chaves_unicas_e_icones_existentes(self):
        chaves = [tema.chave for tema in GUIA]
        assert len(chaves) == len(set(chaves))
        for tema in GUIA:
            if tema.icone:
                assert tema.icone in DESENHOS, f"ícone {tema.icone} não existe"

    def test_pedido_do_usuario_esta_coberto(self):
        # O pedido tinha três partes: mentor explicando telas/campos, guia completo no
        # menu e opção de reativar o uso orientado. Cada uma tem lastro no conteúdo.
        assert {"pdv", "caixa", "produtos", "vendas"} <= set(POR_CHAVE)
        assert sum(len(tema.passos) for tema in GUIA) >= 20
        assert any(tema.campos for tema in GUIA), "nenhum tema explica campos"
        assert any(tema.atalhos for tema in GUIA), "nenhum tema lista atalhos"

    def test_temas_com_modulo_apontam_para_modulos_que_existem(self):
        validos = set(MODULOS) | {MODULO_ADMIN}
        for tema in GUIA:
            if tema.modulo:
                assert tema.modulo in validos, f"tema {tema.chave} → módulo {tema.modulo}"

    def test_tema_do_modulo_cobre_pdv_e_caixa(self):
        assert TEMA_DO_MODULO["PDV"] == "pdv"
        assert TEMA_DO_MODULO["Caixa"] == "caixa"
        assert MODULO_AJUDA not in TEMA_DO_MODULO  # ajuda não é página

    def test_versao_do_guia_positiva(self):
        assert VERSAO_GUIA >= 1


class TestBusca:
    def test_acha_sem_acento_e_sem_caixa(self):
        assert "caixa" in [t.chave for t in buscar("SANGRIA")]
        assert "crediario" in [t.chave for t in buscar("crediário")]
        assert [t.chave for t in buscar("sangria")] == [t.chave for t in buscar("SANGRIÂ")]

    def test_termo_inexistente_devolve_vazio(self):
        assert buscar("xilofone quantico") == ()

    def test_busca_vazia_devolve_tudo(self):
        assert buscar("") == GUIA
        assert buscar("   ") == GUIA

    def test_busca_olha_campos_e_atalhos(self):
        # "F4" só aparece em atalhos; "contado" só em campos.
        assert buscar("F4")
        assert buscar("contado")


class TestHtmlEMarkdown:
    def test_html_nao_deixa_macarrao_de_markdown(self):
        for tema in GUIA:
            html = tema_em_html(tema)
            assert tema.titulo in html
            assert "**" not in html, f"{tema.chave}: negrito markdown sobrou no HTML"
            for passo in tema.passos:
                assert passo.titulo in html

    def test_markdown_tem_todos_os_temas(self):
        texto = guia_em_markdown()
        for tema in GUIA:
            assert tema.titulo in texto
        assert texto.startswith("#")


class TestServico:
    def test_guiado_vem_ligado_no_primeiro_uso(self, cenario):
        servico = ServicoAjuda(cenario.ctx)
        assert servico.guiado_ativo() is True

    def test_desligar_e_ligar_gruda_no_banco(self, cenario):
        servico = ServicoAjuda(cenario.ctx)
        servico.definir_guiado(False)
        assert ServicoAjuda(cenario.ctx).guiado_ativo() is False
        servico.definir_guiado(True)
        assert ServicoAjuda(cenario.ctx).guiado_ativo() is True

    def test_reativar_marca_a_versao_como_vista(self, cenario):
        servico = ServicoAjuda(cenario.ctx)
        servico.definir_guiado(False)
        servico.reativar()
        assert servico.guiado_ativo() is True
        assert servico.versao_vista() == VERSAO_GUIA
        assert servico.versao_mudou() is False

    def test_guia_novo_reaparece(self, cenario):
        servico = ServicoAjuda(cenario.ctx)
        servico.definir_guiado(True)  # grava a versão atual
        assert servico.versao_mudou() is False
        cenario.ctx.parametros.definir(
            CHAVE_VERSAO, str(VERSAO_GUIA - 1), agora_iso=cenario.ctx.agora().isoformat()
        )
        assert servico.versao_mudou() is True

    def test_desligado_continua_desligado_mesmo_com_versao_nova(self, cenario):
        servico = ServicoAjuda(cenario.ctx)
        servico.definir_guiado(False)
        cenario.ctx.parametros.definir(
            CHAVE_VERSAO, "0", agora_iso=cenario.ctx.agora().isoformat()
        )
        assert servico.guiado_ativo() is False

    def test_tema_do_modulo(self, cenario):
        servico = ServicoAjuda(cenario.ctx)
        assert servico.tema_do_modulo("PDV").chave == "pdv"
        assert servico.tema_do_modulo("Caixa").chave == "caixa"
        assert servico.tema_do_modulo("Ajuda") is None
        assert servico.tema_do_modulo("Módulo Inventado") is None

    def test_salvar_markdown_grava_arquivo(self, cenario, tmp_path):
        destino = tmp_path / "guia.md"
        caminho = Path(ServicoAjuda(cenario.ctx).salvar_markdown(str(destino)))
        assert caminho.exists()
        assert caminho.read_text(encoding="utf-8").startswith("#")

    def test_chaves_do_parametro_existem_no_repositorio(self, cenario):
        from bussola_pdv.infra.sqlite.repositorio_usuarios import ParametroRepositorio

        assert CHAVE_GUIADO in ParametroRepositorio.PADROES
        assert CHAVE_VERSAO in ParametroRepositorio.PADROES


class TestAlvosDoMentor:
    def test_todo_passo_aponta_para_campo_real(self, app, cenario):
        """O mentor não pode apontar para campo que não existe na tela."""
        telas = _telas(cenario)
        try:
            for modulo, tela in telas.items():
                tema = mod_ajuda.tema(TEMA_DO_MODULO[modulo])
                assert tema is not None
                for passo in tema.passos:
                    if not passo.alvo:
                        continue
                    assert hasattr(tela, passo.alvo), (
                        f"{modulo}: passo '{passo.titulo}' aponta para "
                        f"'{passo.alvo}', que não existe em {type(tela).__name__}"
                    )
                    assert isinstance(getattr(tela, passo.alvo), QWidget), (
                        f"{modulo}: '{passo.alvo}' não é um widget"
                    )
        finally:
            for tela in telas.values():
                tela.deleteLater()

    def test_alvos_do_tema_inicio_apontam_para_o_pdv(self, app, cenario):
        """O tema "Começando o dia" não tem módulo, mas destaca campos do PDV."""
        tela = _telas(cenario)["PDV"]
        try:
            tema = mod_ajuda.tema("inicio")
            alvos = [passo.alvo for passo in tema.passos if passo.alvo]
            assert alvos
            for alvo in alvos:
                assert hasattr(tela, alvo), f"tema inicio aponta para '{alvo}'"
        finally:
            tela.deleteLater()

    def test_resolve_nomes_para_widgets(self, app, cenario):
        tela = _telas(cenario)["PDV"]
        try:
            tema = mod_ajuda.tema("pdv")
            alvos = alvos_da_tela(tela, tema.passos)
            assert alvos
            assert all(isinstance(widget, QWidget) for widget in alvos.values())
            assert alvos_da_tela(None, tema.passos) == {}
        finally:
            tela.deleteLater()


class TestPainelMentor:
    def _tema(self):
        tema = mod_ajuda.tema("pdv")
        assert tema is not None
        return tema

    def test_anda_para_frente_e_para_tras(self, app):
        painel = PainelMentor()
        try:
            tema = self._tema()
            painel.iniciar(tema, {})
            assert painel.passos == tema.passos
            assert painel.indice == 0
            assert painel.rotulo_contador.text() == f"passo 1 de {len(tema.passos)}"
            painel.proximo()
            assert painel.indice == 1
            painel.anterior()
            assert painel.indice == 0
            painel.anterior()  # no primeiro não vai para -1
            assert painel.indice == 0
        finally:
            painel.deleteLater()

    def test_concluir_no_ultimo_passo_avisa_e_esconde(self, app):
        painel = PainelMentor()
        try:
            tema = self._tema()
            avisos: list[bool] = []
            painel.concluido.connect(lambda: avisos.append(True))
            painel.iniciar(tema, {})
            for _ in range(len(tema.passos) - 1):
                painel.proximo()
            ultimo = painel.indice
            painel.proximo()  # último passo: conclui
            assert avisos == [True]
            assert painel.passos == ()
            assert painel.indice == ultimo
        finally:
            painel.deleteLater()

    def test_parar_avisa_que_o_operador_desligou(self, app):
        painel = PainelMentor()
        try:
            avisos: list[bool] = []
            painel.encerrado.connect(lambda: avisos.append(True))
            painel.iniciar(self._tema(), {})
            painel.botao_parar.click()
            assert avisos == [True]
            assert painel.passos == ()
        finally:
            painel.deleteLater()

    def test_tema_sem_passos_nao_aparece(self, app):
        painel = PainelMentor()
        try:
            painel.iniciar(None, {})
            assert painel.passos == ()
        finally:
            painel.deleteLater()

    def test_destaque_marca_e_desmarca_o_widget(self, app, cenario):
        from bussola_pdv.ui.mentor import PROPRIEDADE_DESTAQUE

        tela = _telas(cenario)["PDV"]
        tela.show()  # alvo invisível não é destacado (não adianta marcar o que não se vê)
        painel = PainelMentor()
        try:
            tema = mod_ajuda.tema("pdv")
            primeiro = next(p for p in tema.passos if p.alvo)
            alvo = getattr(tela, primeiro.alvo)
            painel.iniciar(tema, alvos_da_tela(tela, tema.passos))
            assert alvo.property(PROPRIEDADE_DESTAQUE) == "true"
            painel.parar()
            assert alvo.property(PROPRIEDADE_DESTAQUE) == "false"
        finally:
            painel.deleteLater()
            tela.close()
            tela.deleteLater()


class TestJanelaComAjuda:
    def test_ajuda_esta_no_menu_e_nao_vira_pagina(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.gerente)
        try:
            assert MODULO_AJUDA in janela.modulos
            assert MODULO_AJUDA in DETALHES_MODULO
            assert DETALHES_MODULO[MODULO_AJUDA][0] in DESENHOS
            # a pilha não ganha página para a Ajuda
            assert janela.pilha.count() == len(janela.modulos) - 1
        finally:
            janela.close()
            janela.deleteLater()

    def test_f1_esta_registrado(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.gerente)
        try:
            assert janela.atalho_ajuda.key().toString() == "F1"
        finally:
            janela.close()
            janela.deleteLater()

    def test_mentor_aparece_no_pdv_quando_guiado_esta_ligado(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.gerente)
        try:
            assert janela.mentor.tema is not None
            assert janela.mentor.tema.chave == "pdv"
            assert len(janela.mentor.passos) >= 4
        finally:
            janela.close()
            janela.deleteLater()

    def test_parar_no_mentor_desliga_e_persiste(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.gerente)
        try:
            janela.mentor.botao_parar.click()
            assert janela.mentor.passos == ()
            assert ServicoAjuda(cenario.ctx).guiado_ativo() is False
            # trocar de tela não o traz de volta
            janela._selecionar("Caixa")
            assert janela.mentor.passos == ()
        finally:
            janela.close()
            janela.deleteLater()

    def test_janela_de_ajuda_mostra_guia_e_religa_o_mentor(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        ServicoAjuda(cenario.ctx).definir_guiado(False)
        janela = JanelaPrincipal(cenario.ctx, cenario.gerente)
        try:
            assert janela.mentor.passos == ()
            janela._abrir_ajuda()
            dialogo = janela._janela_ajuda
            assert isinstance(dialogo, JanelaAjuda)
            assert dialogo.temas_visiveis() == [tema.chave for tema in GUIA]
            dialogo.botao_guiado.click()  # reativar
            assert ServicoAjuda(cenario.ctx).guiado_ativo() is True
            assert janela.mentor.tema is not None
            dialogo.close()
        finally:
            janela.close()
            janela.deleteLater()

    def test_filtrar_a_ajuda_mantem_o_tema_escolhido_quando_possivel(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.gerente)
        try:
            janela._abrir_ajuda("caixa")
            dialogo = janela._janela_ajuda
            assert dialogo.tema_atual().chave == "caixa"
            dialogo.campo_busca.setText("sangria")
            assert "caixa" in dialogo.temas_visiveis()
            assert dialogo.tema_atual().chave == "caixa"
            dialogo.campo_busca.setText("xilofone")
            assert "Nada encontrado" in dialogo.rotulo_tema.text()
            dialogo.close()
        finally:
            janela.close()
            janela.deleteLater()
