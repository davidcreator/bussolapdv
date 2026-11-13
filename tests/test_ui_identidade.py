"""Testes dos dois logos oficiais: carregamento, tingimento e quem manda onde.

Os arquivos do logo são versionados (não são gerados por teste), então o que se
prova aqui é o que pode quebrar em silêncio: o caminho dentro do executável
(`sys._MEIPASS`), a tinta tirada da paleta, o logo da loja vencendo o oficial e a
área administrativa **não** aceitando o logo da loja.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "PySide6.QtWidgets", exc_type=ImportError, reason="PySide6 ou libs do Qt ausentes"
)

from bussola_pdv.dominio.marca import Marca, Paleta
from bussola_pdv.ui import identidade

pytestmark = pytest.mark.ui

RAIZ = Path(__file__).resolve().parent.parent
RECURSOS = RAIZ / "src" / "bussola_pdv" / "recursos"


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(["teste-identidade"])


def _data_uri(nome: str) -> str:
    dados = base64.b64encode((RECURSOS / nome).read_bytes()).decode()
    return f"data:image/png;base64,{dados}"


def _cores(pixmap) -> set[tuple[int, int, int, int]]:
    """Todas as cores (RGBA) presentes no pixmap — serve para provar a tinta."""
    imagem = pixmap.toImage()
    cores = set()
    for y in range(imagem.height()):
        for x in range(imagem.width()):
            cor = imagem.pixelColor(x, y)
            cores.add((cor.red(), cor.green(), cor.blue(), cor.alpha()))
    return cores


class TestArquivos:
    def test_os_dois_logos_estao_no_pacote(self):
        assert (RECURSOS / identidade.LOGO_MINI).is_file()
        assert (RECURSOS / identidade.LOGO_COMERCIAL).is_file()

    def test_caminho_do_logo_aponta_para_o_arquivo(self):
        caminho = identidade.caminho_do_logo(identidade.LOGO_MINI)
        assert caminho == RECURSOS / identidade.LOGO_MINI
        assert caminho.stat().st_size > 0

    def test_logo_ausente_vira_erro_claro(self):
        with pytest.raises(FileNotFoundError, match="Logo ausente"):
            identidade.caminho_do_logo("nao_existe.png")


class TestExecutavelCongelado:
    def test_pasta_de_recursos_usa_meipass(self, tmp_path, monkeypatch):
        """No PyInstaller os *datas* ficam em `sys._MEIPASS`, não perto do módulo."""
        congelada = tmp_path / "bussola_pdv" / "recursos"
        congelada.mkdir(parents=True)
        (congelada / identidade.LOGO_MINI).write_bytes(b"png falso")
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        assert identidade.pasta_de_recursos() == congelada
        assert identidade.caminho_do_logo(identidade.LOGO_MINI).parent == congelada

    def test_meipass_sem_a_pasta_cai_no_codigo_fonte(self, tmp_path, monkeypatch):
        """Executável sem o *data* não pode esconder o logo do repositório."""
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        assert identidade.pasta_de_recursos() == RECURSOS


class TestTinta:
    def test_simbolo_recebe_a_cor_primaria(self, app):
        paleta = Paleta(primaria="#B5179E")
        pixmap = identidade.simbolo(lado=30, cor=paleta.primaria)
        assert not pixmap.isNull()
        # O miolo do desenho fica exatamente na tinta da paleta; as bordas
        # suavizadas variam 1-2 no canal por causa do arredondamento do Qt.
        alvo = (0xB5, 0x17, 0x9E)
        visiveis = [cor for cor in _cores(pixmap) if cor[3] > 0]
        assert visiveis
        # O corpo do desenho (alfa 255) é a tinta exata; as bordas suavizadas
        # desviam só na mistura do antialiasing.
        assert {cor for cor in visiveis if cor[3] == 255} == {(*alvo, 255)}
        # E nada do azul do arquivo sobreviveu ao tingimento.
        assert not any(
            abs(vermelho - 0x33) < 20 and abs(verde - 0x44) < 20 for vermelho, verde, _a, _b in visiveis
        )

    def test_logo_oficial_sem_cor_mantem_o_azul_original(self, app):
        pixmap = identidade.pixmap_do_logo(identidade.LOGO_MINI, altura=30)
        opacas = {cor for cor in _cores(pixmap) if cor[3] > 0}
        assert (0x33, 0x44, 0x76, 255) in opacas  # a tinta do arquivo enviado

    @pytest.mark.parametrize("primaria", ["#0D6EFD", "#FDECEF", "#FFEB3B", "#FFFFFF"])
    def test_tinta_do_simbolo_nunca_some_no_quadrado_branco(self, app, primaria):
        """A primária manda na cor — menos quando ela é invisível sobre branco."""
        from bussola_pdv.dominio.marca import razao_contraste
        from bussola_pdv.ui.identidade import tinta_do_simbolo

        tinta = tinta_do_simbolo(primaria)
        assert razao_contraste(tinta, "#FFFFFF") >= 3.0
        if razao_contraste(primaria, "#FFFFFF") >= 3.0:
            assert tinta == primaria  # nada foi mexido sem necessidade

    def test_simbolo_e_quadrado_e_cabe_no_quadrado_do_menu(self, app):
        pixmap = identidade.simbolo(lado=30)
        assert pixmap.width() == pixmap.height()
        assert pixmap.width() / pixmap.devicePixelRatio() == 30

    def test_simbolo_em_tela_hidpi_nao_sai_borrado(self, app):
        pixmap = identidade.simbolo(lado=30, proporcao=2.0)
        assert pixmap.devicePixelRatio() == 2.0
        assert pixmap.width() == 60
        # tamanho lógico continua 30
        assert pixmap.width() / pixmap.devicePixelRatio() == 30


class TestQuemMandaNoLogo:
    def test_sem_logo_da_loja_usa_o_oficial(self, app):
        marca = Marca()
        pixmap = identidade.simbolo(marca, lado=30)
        opacas = {cor for cor in _cores(pixmap) if cor[3] > 0}
        assert (0x33, 0x44, 0x76, 255) in opacas

    def test_logo_da_loja_vence_o_oficial(self, app):
        marca = Marca(nome_fantasia="Loja", logo_data_uri=_data_uri(identidade.LOGO_MINI))
        da_loja = identidade.logo_da_loja(marca, altura=30)
        assert da_loja is not None
        assert not da_loja.isNull()

    def test_admin_ignora_o_logo_da_loja(self, app):
        """Decisão do responsável: a área administrativa é sempre do Bússola."""
        marca = Marca(nome_fantasia="Loja", logo_data_uri=_data_uri(identidade.LOGO_MINI))
        oficial = identidade.simbolo(marca, lado=30, oficial=True)
        opacas = {cor for cor in _cores(oficial) if cor[3] > 0}
        assert (0x33, 0x44, 0x76, 255) in opacas
        assert not identidade.logo_comercial(marca, altura=24).isNull()

        # `oficial=True` devolve a mesma imagem com ou sem logo da loja.
        sem_loja = identidade.simbolo(None, lado=30, oficial=True)
        assert _cores(oficial) == _cores(sem_loja)

    def test_assinatura_comercial_tem_a_proporcao_do_arquivo(self, app):
        pixmap = identidade.logo_comercial(altura=34)
        escala = pixmap.width() / pixmap.height()
        assert escala == pytest.approx(identidade.PROPORCAO_COMERCIAL, rel=0.02)


class TestDataUri:
    def test_aceita_png_em_base64(self, app):
        pixmap = identidade.pixmap_de_data_uri(_data_uri(identidade.LOGO_MINI), altura=24)
        assert pixmap is not None
        assert not pixmap.isNull()

    @pytest.mark.parametrize(
        "dados",
        [
            "",
            "data:image/jpeg;base64,AAAA",  # formato não suportado
            "data:image/png;base64,@@@nao-e-base64@@@",
            "data:image/png;base64," + base64.b64encode(b"nao sou png").decode(),
        ],
    )
    def test_recusa_lixo_sem_estourar(self, app, dados):
        assert identidade.pixmap_de_data_uri(dados, altura=24) is None


class TestRotuloLogo:
    def test_altura_fixa_e_pixmap_proporcional(self, app):
        rotulo = identidade.RotuloLogo(identidade.LOGO_COMERCIAL, altura=34)
        assert rotulo.minimumHeight() == 34
        pixmap = rotulo.pixmap()
        assert pixmap is not None
        assert not pixmap.isNull()
        assert pixmap.height() / pixmap.devicePixelRatio() == 34
        assert rotulo.sizeHint().height() == 34

    def test_marca_trocada_regera_a_imagem(self, app):
        def pixels(rotulo) -> bytes:
            imagem = rotulo.pixmap().toImage()
            return bytes(imagem.constBits())

        rotulo = identidade.RotuloLogo(identidade.LOGO_COMERCIAL, altura=24)
        antes = pixels(rotulo)
        rotulo.definir_marca(
            Marca(nome_fantasia="Loja", logo_data_uri=_data_uri(identidade.LOGO_MINI))
        )
        assert pixels(rotulo) != antes
        # Sem logo da loja, volta exatamente o oficial.
        rotulo.definir_marca(None)
        assert pixels(rotulo) == antes


class TestIconeDoPrograma:
    def test_aplicacao_carrega_o_logo_mini_como_icone(self, app):
        from bussola_pdv.ui.app import criar_aplicacao

        aplicacao = criar_aplicacao(["teste-icone"])
        icone = aplicacao.windowIcon()
        assert not icone.isNull()
        # O Qt serve a única resolução do PNG (450×450); o Windows reduz.
        assert {tamanho.width() for tamanho in icone.availableSizes()} == {450}
        assert icone.pixmap(32, 32).width() == 32
