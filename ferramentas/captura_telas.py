"""Gera capturas de tela da interface (Qt offscreen), sem depender de servidor gráfico.

Uso:  QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 ferramentas/captura_telas.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QDate, QTimer

from bussola_pdv.aplicacao.ajuda import ServicoAjuda
from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.aplicacao.marca import ServicoMarca
from bussola_pdv.dominio.marca import Marca
from bussola_pdv.infra.massa_demo import popular, relogio_demo
from bussola_pdv.ui.admin.janela import JanelaAdmin
from bussola_pdv.ui.app import criar_aplicacao
from bussola_pdv.ui.janela import JanelaPrincipal
from bussola_pdv.ui.login import DialogoLogin

SAIDA = Path(__file__).resolve().parents[1] / "docs" / "capturas"


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    banco = Path("/tmp/bussola_demo_captura.db")
    if banco.exists():
        banco.unlink()
    ctx = Contexto.abrir(banco, relogio=relogio_demo())
    popular(ctx)
    # As capturas "comuns" saem sem a faixa do mentor, como as versões anteriores:
    # quem mostra o mentor são as capturas 30 e 31, e misturar as duas coisas
    # esconderia o conteúdo das telas na documentação.
    ServicoAjuda(ctx).definir_guiado(False)

    app = criar_aplicacao(["captura"])
    operador = ctx.usuarios.por_login("operador")

    janela = JanelaPrincipal(ctx, operador)
    janela.resize(1280, 820)
    janela.show()

    def capturar(nome: str) -> None:
        # dois ciclos: o recolher/expandir da sidebar reajusta a geometria depois
        app.processEvents()
        app.processEvents()
        pix = janela.grab()
        pix.save(str(SAIDA / f"{nome}.png"))
        print("captura:", SAIDA / f"{nome}.png")

    capturar("01_pdv_vazio")

    # Simula lançamento de itens no PDV.
    janela.tela_pdv.campo_codigo.setText("P001")
    janela.tela_pdv.campo_quantidade.setText("2")
    janela.tela_pdv._adicionar_item()
    codigo_barras = ctx.produtos.por_codigo("P002").codigo_barras
    janela.tela_pdv.campo_codigo.setText(codigo_barras)
    janela.tela_pdv.campo_quantidade.setText("3")
    janela.tela_pdv._adicionar_item()
    capturar("02_pdv_com_itens")

    for indice, nome in [(1, "03_caixa"), (2, "04_produtos"), (5, "06_auditoria")]:
        janela.navegacao.setCurrentRow(indice)
        app.processEvents()
        capturar(nome)

    # Fechamento com sessão de gerente: é a tela onde mora o botão Exportar,
    # que o perfil Atendente (usado nas demais capturas) não vê.
    gerente = ctx.usuarios.por_login("gerente")
    janela_gerente = JanelaPrincipal(ctx, gerente)
    janela_gerente.resize(1280, 820)
    janela_gerente.show()
    janela_gerente.navegacao.setCurrentRow(4)
    tela_fechamento = janela_gerente.pilha.widget(4)
    tela_fechamento.data.setDate(QDate(2026, 11, 11))  # dia com movimento na demo
    tela_fechamento._gerar()
    app.processEvents()
    app.processEvents()
    janela_gerente.grab().save(str(SAIDA / "05_fechamento.png"))
    print("captura:", SAIDA / "05_fechamento.png")

    # Módulos que saíram do placeholder na v0.6.0 (a mesma sessão de gerente,
    # porque é ela que enxerga o botão Exportar em cada tela).
    for indice, nome in ((6, "16_clientes"), (7, "17_crediario"), (8, "18_estoque")):
        janela_gerente.navegacao.setCurrentRow(indice)
        app.processEvents()
        app.processEvents()
        janela_gerente.grab().save(str(SAIDA / f"{nome}.png"))
        print("captura:", SAIDA / f"{nome}.png")

    # Caixa com turno aberto: mostra o Exportar do turno ao lado dos movimentos.
    janela_gerente.navegacao.setCurrentRow(1)
    app.processEvents()
    app.processEvents()
    janela_gerente.grab().save(str(SAIDA / "19_caixa_exportar.png"))
    print("captura:", SAIDA / "19_caixa_exportar.png")

    # Prévia de impressão (v0.8.0): o cupom desenhado no papel escolhido.
    from bussola_pdv.aplicacao.impressao import ServicoImpressao
    from bussola_pdv.dominio.impressao import Papel
    from bussola_pdv.ui.impressao import DialogoPreviaImpressao

    impressao = ServicoImpressao(ctx)
    venda = ctx.vendas.listar(limite=1)
    if venda:
        documento = impressao.comprovante_por_id(str(venda[0]["id"]), papel=Papel.BOBINA_80)
        previa = DialogoPreviaImpressao(documento, impressao, ator=janela_gerente.usuario, parent=janela_gerente)
        previa.show()
        app.processEvents()
        app.processEvents()
        previa.grab().save(str(SAIDA / "24_impressao_previa.png"))
        print("captura:", SAIDA / "24_impressao_previa.png")
        previa.close()
    janela_gerente.close()

    # Área administrativa (sessão do Admin Master).
    master = ctx.usuarios.por_login("master")
    admin_janela = JanelaAdmin(ctx, master)
    admin_janela.resize(1120, 760)
    admin_janela.show()

    def capturar_admin(nome: str, chave: str) -> None:
        chaves = admin_janela.secoes_liberadas()
        admin_janela.menu.setCurrentRow(chaves.index(chave))
        app.processEvents()
        app.processEvents()
        admin_janela.grab().save(str(SAIDA / f"{nome}.png"))
        print("captura:", SAIDA / f"{nome}.png")

    capturar_admin("08_admin_dependencias", "dependencias")
    capturar_admin("09_admin_marca", "marca")
    capturar_admin("10_admin_usuarios", "usuarios")
    capturar_admin("11_admin_permissoes", "permissoes")
    capturar_admin("12_admin_parametros", "parametros")
    capturar_admin("13_admin_manutencao", "manutencao")

    # Grupo "Impressão" dos parâmetros: fica no fim da seção, então rola até lá.
    from PySide6.QtWidgets import QScrollArea

    admin_janela.menu.setCurrentRow(admin_janela.secoes_liberadas().index("parametros"))
    app.processEvents()
    for area in admin_janela.findChildren(QScrollArea):
        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
    app.processEvents()
    app.processEvents()
    admin_janela.grab().save(str(SAIDA / "25_admin_impressao.png"))
    print("captura:", SAIDA / "25_admin_impressao.png")
    admin_janela.close()

    # Menu recolhido: a mesma tela com a sidebar só de ícones.
    janela.navegacao.setCurrentRow(0)
    janela.barra_superior.botao_menu.click()
    app.processEvents()
    capturar("15_menu_recolhido")
    janela.barra_superior.botao_menu.click()
    app.processEvents()

    # Tela de login (antes de trocar o tema, para registrar a skin padrão).
    login = DialogoLogin(ctx)
    login.show()
    app.processEvents()
    login.grab().save(str(SAIDA / "07_login.png"))
    print("captura:", SAIDA / "07_login.png")
    login.close()

    # Tema personalizado: troca de cores da marca e reaplica em toda a interface.
    ServicoMarca(ctx).salvar(
        master,
        Marca(
            nome_fantasia="Mercado Bom Preço",
            razao_social="Mercado Bom Preço Ltda.",
            cnpj="12.345.678/0001-90",
            rodape_comprovante="Obrigado pela preferência!",
        ).com_cores(primaria="#1D5B4C", primaria_escura="#14453A", secundaria="#C2410C", destaque="#F2B705"),
    )
    janela._aplicar_marca()
    janela.show()
    app.processEvents()
    capturar("14_tema_personalizado")

    janela.close()

    # Primeiro uso: a tela onde se escolhe a pasta de dados (v0.6.1).
    from bussola_pdv.ui.primeiro_uso import DialogoPrimeiroUso

    primeiro = DialogoPrimeiroUso(SAIDA.parent.parent / "dados-exemplo" / "pdv.db")
    primeiro.campo_loja.setText("Loja de Demonstração")
    primeiro.campo_login.setText("master")
    primeiro.campo_nome.setText("Dora Proprietária")
    primeiro.campo_senha.setText("exemplo-ficticio")
    primeiro.campo_senha2.setText("exemplo-ficticio")
    primeiro.show()
    app.processEvents()
    app.processEvents()
    primeiro.grab().save(str(SAIDA / "20_primeiro_uso.png"))
    print("captura:", SAIDA / "20_primeiro_uso.png")
    primeiro.close()

    capturar_compacto(app, banco)
    capturar_escala(app, banco)
    capturar_ajuda(app, banco)

    ctx.fechar()
    QTimer.singleShot(0, app.quit)
    return 0


def capturar_compacto(app, banco: Path) -> None:
    """Capturas na faixa compacta (800×600), a mesma que roda em monitor de balcão.

    Ficam ao lado das capturas em 1280×820 de propósito: é a comparação que mostra a
    interface se reorganizando (sidebar recolhida, indicadores 2 por linha, cartões
    com as ferramentas na segunda linha).
    """
    ctx = Contexto.abrir(banco, relogio=relogio_demo())
    janela = JanelaPrincipal(ctx, ctx.usuarios.por_login("gerente"))
    janela.resize(800, 600)
    janela.show()
    app.processEvents()

    def capturar_apos(nome: str, modulo: str) -> None:
        janela._selecionar(modulo)
        # o ajuste de colunas espera 150 ms: sem a espera a captura sai no meio
        fim = time.monotonic() + 0.4
        while time.monotonic() < fim:
            app.processEvents()
        janela.grab().save(str(SAIDA / f"{nome}.png"))
        print("captura:", SAIDA / f"{nome}.png")

    janela._selecionar("PDV")
    fim = time.monotonic() + 0.4
    while time.monotonic() < fim:
        app.processEvents()
    capturar_apos("21_pdv_800x600", "PDV")
    capturar_apos("22_produtos_800x600", "Produtos")
    capturar_apos("23_caixa_800x600", "Caixa")
    janela.close()
    ctx.fechar()


def capturar_escala(app, banco: Path) -> None:
    """Capturas em 911×512 — o que sobra de tela em 1366×768 com escala de 150%.

    É a prova visual de que a janela abre **dentro** do monitor e de que o conteúdo
    acompanha: sidebar na faixa média, indicadores em 3 colunas, pagamento e
    finalização legíveis, nada cortado na borda.
    """
    ctx = Contexto.abrir(banco, relogio=relogio_demo())
    janela = JanelaPrincipal(ctx, ctx.usuarios.por_login("gerente"))
    janela.resize(911, 512)
    janela.show()
    fim = time.monotonic() + 0.4
    while time.monotonic() < fim:
        app.processEvents()
    janela.grab().save(str(SAIDA / "28_pdv_911x512.png"))
    print("captura:", SAIDA / "28_pdv_911x512.png")
    janela._selecionar("Vendas")
    fim = time.monotonic() + 0.4
    while time.monotonic() < fim:
        app.processEvents()
    janela.grab().save(str(SAIDA / "29_vendas_911x512.png"))
    print("captura:", SAIDA / "29_vendas_911x512.png")
    janela.close()
    ctx.fechar()


def capturar_ajuda(app, banco: Path) -> None:
    """Capturas do mentor e do guia (v0.10.0).

    O mentor aparece porque o uso orientado vem ligado no primeiro uso; a captura da
    janela de Ajuda é feita com o diálogo **mostrado** (e não só construído), senão
    sairia um retângulo vazio.
    """
    ctx = Contexto.abrir(banco, relogio=relogio_demo())
    ServicoAjuda(ctx).definir_guiado(True)  # é esta a captura do mentor
    janela = JanelaPrincipal(ctx, ctx.usuarios.por_login("gerente"))
    janela.resize(1280, 820)
    janela.show()
    fim = time.monotonic() + 0.5
    while time.monotonic() < fim:
        app.processEvents()
    janela.grab().save(str(SAIDA / "30_mentor_pdv.png"))
    print("captura:", SAIDA / "30_mentor_pdv.png")

    janela._selecionar("Caixa")
    fim = time.monotonic() + 0.4
    while time.monotonic() < fim:
        app.processEvents()
    janela.grab().save(str(SAIDA / "31_mentor_caixa.png"))
    print("captura:", SAIDA / "31_mentor_caixa.png")

    janela._abrir_ajuda("caixa")
    ajuda = janela._janela_ajuda
    if ajuda is not None:
        ajuda.show()
        fim = time.monotonic() + 0.4
        while time.monotonic() < fim:
            app.processEvents()
        ajuda.grab().save(str(SAIDA / "32_ajuda_guia.png"))
        print("captura:", SAIDA / "32_ajuda_guia.png")
        # A segunda captura mostra as duas coisas que o pedido citou: a busca do guia
        # e o modo guiado **desligado**, com o botão que o religa à vista.
        ajuda.campo_busca.setText("sangria")
        ajuda._alternar_guiado()
        app.processEvents()
        ajuda.grab().save(str(SAIDA / "33_ajuda_busca.png"))
        print("captura:", SAIDA / "33_ajuda_busca.png")
        ajuda.close()
    janela.close()
    ServicoAjuda(ctx).definir_guiado(False)  # devolve a base ao estado das outras capturas
    ctx.fechar()


if __name__ == "__main__":
    raise SystemExit(main())
