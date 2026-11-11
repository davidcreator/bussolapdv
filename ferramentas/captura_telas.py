"""Gera capturas de tela da interface (Qt offscreen), sem depender de servidor gráfico.

Uso:  QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 ferramentas/captura_telas.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QTimer  # noqa: E402

from bussola_pdv.aplicacao.contexto import Contexto  # noqa: E402
from bussola_pdv.dominio.relogio import RelogioFixo  # noqa: E402
from bussola_pdv.infra.massa_demo import popular, relogio_demo  # noqa: E402
from bussola_pdv.dominio.marca import Marca  # noqa: E402
from bussola_pdv.aplicacao.marca import ServicoMarca  # noqa: E402
from bussola_pdv.ui.admin.janela import JanelaAdmin  # noqa: E402
from bussola_pdv.ui.app import criar_aplicacao  # noqa: E402
from bussola_pdv.ui.janela import JanelaPrincipal  # noqa: E402
from bussola_pdv.ui.login import DialogoLogin  # noqa: E402

SAIDA = Path(__file__).resolve().parents[1] / "docs" / "capturas"


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    banco = Path("/tmp/bussola_demo_captura.db")
    if banco.exists():
        banco.unlink()
    ctx = Contexto.abrir(banco, relogio=relogio_demo())
    popular(ctx)

    app = criar_aplicacao(["captura"])
    operador = ctx.usuarios.por_login("operador")

    janela = JanelaPrincipal(ctx, operador)
    janela.resize(1280, 800)
    janela.show()

    def capturar(nome: str) -> None:
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

    for indice, nome in [(1, "03_caixa"), (2, "04_produtos"), (4, "05_fechamento"), (5, "06_auditoria")]:
        janela.navegacao.setCurrentRow(indice)
        app.processEvents()
        capturar(nome)

    # Área administrativa (sessão do Admin Master).
    master = ctx.usuarios.por_login("master")
    admin_janela = JanelaAdmin(ctx, master)
    admin_janela.resize(1120, 760)
    admin_janela.show()

    def capturar_admin(nome: str, chave: str) -> None:
        chaves = admin_janela.secoes_liberadas()
        admin_janela.menu.setCurrentRow(chaves.index(chave))
        app.processEvents()
        admin_janela.grab().save(str(SAIDA / f"{nome}.png"))
        print("captura:", SAIDA / f"{nome}.png")

    capturar_admin("08_admin_dependencias", "dependencias")
    capturar_admin("09_admin_marca", "marca")
    capturar_admin("10_admin_usuarios", "usuarios")
    capturar_admin("11_admin_permissoes", "permissoes")
    capturar_admin("12_admin_parametros", "parametros")
    capturar_admin("13_admin_manutencao", "manutencao")
    admin_janela.close()

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

    # Tela de login.
    janela.close()
    login = DialogoLogin(ctx)
    login.show()
    app.processEvents()
    login.grab().save(str(SAIDA / "07_login.png"))
    print("captura:", SAIDA / "07_login.png")
    login.close()
    ctx.fechar()
    QTimer.singleShot(0, app.quit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
