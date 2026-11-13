"""Folha de estilo no vocabulário do AdminLTE, gerada a partir da paleta da loja.

A referência é o AdminLTE (admin dashboard em Bootstrap, MIT): sidebar escura com
a marca no topo, painel do usuário, menu com ícones, barra superior, cabeçalho de
página com trilha, cartões brancos sobre um fundo cinza-azulado e *small-boxes*
coloridas para indicadores. Nenhum CSS do projeto é copiado — o que se aproveita é
a **linguagem visual** (hierarquia, densidade, cantos de 4 px, sombras discretas),
reconstruída aqui em Qt Style Sheets e alimentada pela paleta da loja.

Duas garantias continuam valendo, como no resto do projeto:

* **cor é dado**: a paleta vem de `Marca` (tabela `parametros`) e é interpolada;
* **contraste é requisito**: quando o branco sobre a primária não passa, o texto do
  botão vira escuro em vez de sumir.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..dominio.marca import FONTE_PADRAO, Marca, Paleta, garantir_contraste, tinta_sobre

if TYPE_CHECKING:  # a paleta só é construída quando há Qt de verdade
    from PySide6.QtGui import QPalette

#: Paleta padrão exposta como constantes para telas e testes que precisam de cor solta.
_PADRAO = Paleta()
GRAFITE = _PADRAO.primaria
GRAFITE_ESCURO = _PADRAO.primaria_escura
TURQUESA = _PADRAO.secundaria
TURQUESA_CLARA = _PADRAO.secundaria_clara
AMBAR = _PADRAO.destaque
ENTRADA = _PADRAO.entrada
CALCULADA = "#F2F3F5"
TEXTO = _PADRAO.texto
TEXTO_SUAVE = _PADRAO.texto_suave
SUCESSO = _PADRAO.sucesso
ALERTA = _PADRAO.alerta
ERRO = _PADRAO.erro
BORDA = _PADRAO.borda

FONTE = FONTE_PADRAO

#: Paleta corrente: atualizada quando a folha é gerada, para ícones e indicadores.
_PALETA_CORRENTE = Paleta()


def _misturar(cor: str, outra: str = "#FFFFFF", fator: float = 0.15) -> str:
    """Mistura dois hexadecimais (usado para estados hover, sem tabela de cores)."""
    canais = []
    for inicio in (1, 3, 5):
        a = int(cor[inicio : inicio + 2], 16)
        b = int(outra[inicio : inicio + 2], 16)
        canais.append(round(a + (b - a) * fator))
    return "#" + "".join(f"{canal:02X}" for canal in canais)


def misturar(cor: str, outra: str = "#FFFFFF", fator: float = 0.15) -> str:
    """Mistura dois hexadecimais (hover, tons de texto sobre a sidebar)."""
    return _misturar(cor, outra, fator)


def paleta_corrente() -> Paleta:
    return _PALETA_CORRENTE


def definir_paleta_corrente(paleta: Paleta) -> None:
    global _PALETA_CORRENTE
    _PALETA_CORRENTE = paleta


def cores_tonalidade(paleta: Paleta | None = None) -> dict[str, str]:
    """Cor de destaque de cada tonalidade de indicador/etiqueta."""
    p = paleta or _PALETA_CORRENTE
    return {
        "primaria": p.primaria,
        "secundaria": p.secundaria,
        "info": p.secundaria,
        "sucesso": p.sucesso,
        "alerta": p.alerta,
        "erro": p.erro,
        "destaque": p.destaque,
        "claro": p.texto_suave,
    }


#: Compatibilidade: mapa de tonalidades da paleta padrão.
CORES_TONALIDADE = cores_tonalidade(Paleta())


def cor_da_tonalidade(nome: str) -> str:
    return cores_tonalidade().get(nome, _PALETA_CORRENTE.primaria)


def folha_estilo(paleta: Paleta | None = None, fonte: str | None = None) -> str:
    """QSS completo. Recebe paleta e fonte já validadas pelo domínio."""
    p = paleta or Paleta()
    definir_paleta_corrente(p)
    familia = fonte or FONTE_PADRAO

    branco = "#FFFFFF"
    # Tinta do botão pela razão de contraste: dourado/verde-claro pedem texto
    # escuro; azul escuro pede texto branco. Antes o critério era só "3:1".
    texto_botao = tinta_sobre(p.primaria, escura=p.texto)
    # Texto secundário nunca abaixo de 4,5:1 sobre o fundo da janela (o pior caso,
    # porque cartões são brancos). Vale para qualquer paleta que a loja escolher.
    suave = garantir_contraste(p.texto_suave, p.fundo, alvo=4.5)
    # Derivadas da sidebar (o AdminLTE escurece/clareia a mesma tinta).
    lateral = p.primaria_escura
    lateral_hover = _misturar(lateral, branco, 0.10)
    lateral_ativo = _misturar(lateral, branco, 0.16)
    lateral_texto = _misturar(lateral, branco, 0.78)
    lateral_borda = _misturar(lateral, branco, 0.14)
    marca_fundo = p.primaria
    marca_fundo_alt = _misturar(p.primaria, "#000000", 0.08)
    topo_fundo = branco
    sombra_linha = p.borda
    cabecalho_tabela = _misturar(p.fundo, "#000000", 0.03)
    hover_botao = _misturar(p.primaria, branco, 0.12)
    selecao_tabela = _misturar(p.primaria, branco, 0.86)
    linha_alternada = _misturar(p.fundo, "#000000", 0.015)
    calculada = _misturar(p.fundo, "#000000", 0.06)
    desabilitado = _misturar(p.fundo, "#000000", 0.04)

    return f"""
/* ---------- base ---------- */
QWidget {{
    font-family: "{familia}", "DejaVu Sans", sans-serif;
    font-size: 9.5pt;
    color: {p.texto};
}}
QMainWindow, QDialog {{ background: {p.fundo}; }}
#conteudo {{ background: {p.fundo}; }}

/* ---------- barra lateral (sidebar) ---------- */
#barraLateral {{
    background: {lateral};
    border: none;
}}
#marcaBarra {{
    background: {marca_fundo};
    border-bottom: 1px solid {marca_fundo_alt};
}}
#monograma {{
    background: {branco};
    color: {p.primaria};
    border-radius: 4px;
    font-size: 12pt;
    font-weight: 700;
}}
#marcaNome {{
    color: {branco};
    font-size: 10pt;
    font-weight: 600;
}}
#marcaVersao {{
    color: {_misturar(marca_fundo, branco, 0.70)};
    font-size: 7.5pt;
}}
#painelUsuario {{
    background: {_misturar(lateral, "#FFFFFF", 0.05)};
    border-bottom: 1px solid {lateral_borda};
}}
#avatar {{
    background: {_misturar(p.primaria, branco, 0.72)};
    color: {p.primaria_escura};
    border-radius: 16px;
    font-size: 9pt;
    font-weight: 700;
}}
#usuarioNome {{
    color: {branco};
    font-size: 9pt;
    font-weight: 600;
}}
#usuarioPerfil {{
    color: {lateral_texto};
    font-size: 8pt;
}}
#barraLateralRodape {{
    color: {_misturar(lateral, branco, 0.45)};
    font-size: 7.5pt;
    border-top: 1px solid {lateral_borda};
}}

QListWidget#navegacao {{
    background: {lateral};
    border: none;
    outline: none;
    padding: 6px 0;
}}
QListWidget#navegacao::item {{
    color: {lateral_texto};
    padding: 8px 12px;
    border-left: 3px solid transparent;
    font-size: 9.5pt;
}}
QListWidget#navegacao::item:hover {{
    background: {lateral_hover};
    color: {branco};
}}
QListWidget#navegacao::item:selected {{
    background: {lateral_ativo};
    color: {branco};
    border-left: 3px solid {p.destaque};
    font-weight: 600;
}}

/* ---------- barra superior ---------- */
#barraSuperior {{
    background: {topo_fundo};
    border-bottom: 1px solid {sombra_linha};
}}
#barraSuperiorTitulo {{
    color: {p.texto};
    font-size: 10pt;
    font-weight: 600;
}}
#chipUsuario {{
    background: {p.fundo};
    color: {suave};
    border: 1px solid {p.borda};
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 8pt;
}}
QPushButton#botaoMenu {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 0;
}}
QPushButton#botaoMenu:hover {{ background: {p.fundo}; }}

/* ---------- cabeçalho de conteúdo ---------- */
#cabecalhoConteudo {{ background: transparent; }}
#tituloConteudo {{
    color: {p.texto};
    font-size: 14pt;
    font-weight: 600;
}}
#descricaoConteudo {{
    color: {suave};
    font-size: 8.5pt;
}}
#trilhaConteudo {{
    color: {suave};
    font-size: 8pt;
    padding-top: 4px;
}}

/* ---------- cartões ---------- */
#cartao {{
    background: {p.superficie};
    border: 1px solid {sombra_linha};
    border-radius: 4px;
}}
#cartaoCabecalho {{
    background: {p.superficie};
    border-bottom: 1px solid {sombra_linha};
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
#cartaoTitulo {{
    color: {p.texto};
    font-size: 10pt;
    font-weight: 600;
}}
#cartaoSubtitulo {{
    color: {suave};
    font-size: 8pt;
}}
#tituloSecao {{
    color: {suave};
    font-size: 7.5pt;
    font-weight: 700;
    padding: 2px 0;
}}

/* QGroupBox vira cartão: mesma linguagem, sem tocar nas telas existentes */
QGroupBox {{
    background: {p.superficie};
    border: 1px solid {sombra_linha};
    border-radius: 4px;
    margin-top: 7px;
    padding: 6px 9px 6px 9px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 7px;
    padding: 0 6px;
    color: {suave};
    background: {p.superficie};
    font-size: 8pt;
    font-weight: 700;
}}

/* ---------- caixas de indicador (small-box) ---------- */
#caixaInfo {{
    background: {p.superficie};
    border: 1px solid {sombra_linha};
    border-left: 4px solid {p.primaria};
    border-radius: 4px;
}}
#caixaInfo[tonalidade="secundaria"], #caixaInfo[tonalidade="info"] {{
    border-left-color: {p.secundaria};
}}
#caixaInfo[tonalidade="sucesso"] {{ border-left-color: {p.sucesso}; }}
#caixaInfo[tonalidade="alerta"] {{ border-left-color: {p.alerta}; }}
#caixaInfo[tonalidade="erro"] {{ border-left-color: {p.erro}; }}
#caixaInfo[tonalidade="destaque"] {{ border-left-color: {p.destaque}; }}
#caixaInfoRotulo {{
    color: {suave};
    font-size: 7.5pt;
    font-weight: 700;
}}
#caixaInfoValor {{
    color: {p.texto};
    font-size: 16pt;
    font-weight: 700;
}}
#caixaInfoLegenda {{
    color: {suave};
    font-size: 8pt;
}}
#caixaInfoIcone {{ background: transparent; }}

/* ---------- etiquetas (badge) ---------- */
#selo {{
    border-radius: 9px;
    padding: 2px 9px;
    font-size: 7.5pt;
    font-weight: 700;
}}
#selo[tonalidade="claro"] {{
    background: {p.fundo};
    color: {suave};
    border: 1px solid {p.borda};
}}
#selo[tonalidade="primaria"] {{ background: {_misturar(p.primaria, "#FFFFFF", 0.86)}; color: {p.primaria}; }}
#selo[tonalidade="sucesso"] {{ background: {_misturar(p.sucesso, "#FFFFFF", 0.84)}; color: {p.sucesso}; }}
#selo[tonalidade="alerta"] {{ background: {_misturar(p.destaque, "#FFFFFF", 0.72)}; color: {p.alerta}; }}
#selo[tonalidade="erro"] {{ background: {_misturar(p.erro, "#FFFFFF", 0.86)}; color: {p.erro}; }}
#selo[tonalidade="info"], #selo[tonalidade="secundaria"] {{
    background: {_misturar(p.secundaria, "#FFFFFF", 0.84)};
    color: {_misturar(p.secundaria, "#000000", 0.25)};
}}

/* ---------- botões ---------- */
QPushButton {{
    background: {p.primaria};
    color: {texto_botao};
    border: 1px solid {p.primaria};
    border-radius: 4px;
    padding: 6px 13px;
    font-size: 9pt;
    font-weight: 600;
}}
QPushButton:hover {{ background: {hover_botao}; border-color: {hover_botao}; }}
QPushButton:pressed {{ background: {p.primaria_escura}; }}
QPushButton:focus {{ border: 1px solid {p.destaque}; }}
QPushButton:disabled {{
    background: {desabilitado};
    border-color: {p.borda};
    color: {suave};
}}
QPushButton#secundario {{
    background: {p.superficie};
    color: {p.texto};
    border: 1px solid {p.borda};
}}
QPushButton#secundario:hover {{ background: {p.fundo}; }}
QPushButton#perigo {{ background: {p.erro}; border-color: {p.erro}; color: {branco}; }}
QPushButton#perigo:hover {{ background: {_misturar(p.erro, "#FFFFFF", 0.12)}; }}
QPushButton#sucesso {{ background: {p.sucesso}; border-color: {p.sucesso}; color: {branco}; }}
QPushButton#aviso {{ background: {p.destaque}; border-color: {p.destaque}; color: {p.texto}; }}
QPushButton#link {{
    background: transparent;
    border: none;
    color: {p.primaria};
    font-weight: 600;
    padding: 4px 6px;
}}

/* ---------- formulários ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit, QTextEdit {{
    background: {p.entrada};
    border: 1px solid {_misturar(p.borda, "#000000", 0.12)};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {p.primaria};
    selection-color: {branco};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {p.primaria};
}}
QLineEdit:read-only, QLineEdit[calculado="true"] {{
    background: {calculada};
    border: 1px solid {p.borda};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: {desabilitado};
    color: {suave};
}}
QComboBox {{ padding-right: 20px; }}
/* Respiro no `QSpinBox`: as setas ficam dentro da moldura e o dígito não passa
   por baixo delas (relato da conferência de gaveta, campo de quantidade cortado). */
QSpinBox, QDoubleSpinBox {{ padding-right: 16px; min-height: 20px; }}
QComboBox QAbstractItemView {{
    background: {p.superficie};
    border: 1px solid {p.borda};
    selection-background-color: {selecao_tabela};
    selection-color: {p.texto};
    outline: none;
}}
QCheckBox, QRadioButton {{ background: transparent; spacing: 6px; }}
QLabel {{ background: transparent; }}

/* ---------- tabelas ---------- */
QTableWidget, QTableView, QTreeWidget, QListWidget#listaSimples {{
    background: {p.superficie};
    alternate-background-color: {linha_alternada};
    gridline-color: {_misturar(p.borda, "#FFFFFF", 0.45)};
    border: 1px solid {sombra_linha};
    border-radius: 4px;
    selection-background-color: {selecao_tabela};
    selection-color: {p.texto};
    outline: none;
}}
QTableWidget::item, QTableView::item {{ padding: 4px 6px; }}
QHeaderView::section {{
    background: {cabecalho_tabela};
    color: {suave};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {p.borda};
    border-right: 1px solid {_misturar(p.borda, "#FFFFFF", 0.5)};
    font-size: 8pt;
    font-weight: 700;
}}
QTableCornerButton::section {{ background: {cabecalho_tabela}; border: none; }}
QTabWidget::pane {{ border: 1px solid {sombra_linha}; border-radius: 4px; background: {p.superficie}; }}
QTabBar::tab {{
    background: {p.fundo};
    color: {suave};
    padding: 6px 14px;
    border: 1px solid {sombra_linha};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{ background: {p.superficie}; color: {p.texto}; font-weight: 600; }}

/* ---------- textos auxiliares ---------- */
#totalCupom {{
    font-size: 20pt;
    font-weight: 700;
    color: {p.primaria};
    background: {p.fundo};
    border: 1px solid {sombra_linha};
    border-radius: 4px;
    padding: 6px 12px;
}}
#mensagemOk {{ color: {p.sucesso}; font-weight: 600; }}
#mensagemAlerta {{ color: {p.alerta}; font-weight: 600; }}
#mensagemErro {{ color: {p.erro}; font-weight: 600; }}
#textoAjuda {{ color: {suave}; font-size: 8.5pt; }}
#destaqueAdmin {{ color: {p.primaria}; font-weight: 700; font-size: 12pt; }}

/* ---------- ajuda e mentor (v0.10.0) ---------- */
#tituloAjuda {{
    color: {p.texto};
    font-size: 16pt;
    font-weight: 700;
}}
#conteudoAjuda {{
    background: {p.superficie};
    color: {p.texto};
    padding: 14px 16px;
}}
QListWidget#indiceAjuda {{
    background: {p.superficie};
    border: 1px solid {p.borda};
    border-radius: 4px;
    outline: none;
    padding: 4px;
}}
QListWidget#indiceAjuda::item {{
    padding: 7px 8px;
    border-radius: 4px;
    color: {p.texto};
}}
QListWidget#indiceAjuda::item:selected {{
    background: {selecao_tabela};
    color: {p.texto};
    font-weight: 600;
}}
QScrollArea#rolagemAjuda, QScrollArea#rolagemAjuda > QWidget > QWidget {{
    background: {p.superficie};
    border: 1px solid {p.borda};
    border-radius: 4px;
}}
/* Faixa do mentor: mesma família visual das cartas, com a cor de destaque na
   borda esquerda para não competir com o conteúdo. */
#painelMentor {{
    background: {selecao_tabela};
    border-top: 2px solid {p.primaria};
}}
#mentorTitulo {{
    color: {p.texto};
    font-size: 9.5pt;
    font-weight: 700;
}}
#mentorTexto {{ color: {p.texto}; font-size: 9pt; }}
#mentorContador {{ color: {suave}; font-size: 8pt; }}

/* Destaque do alvo do passo: borda visível, sem mexer no tamanho da tela. */
*[destaqueMentor="true"] {{
    border: 2px solid {p.destaque};
    border-radius: 4px;
}}

/* ---------- rodapé, status e diversos ---------- */
#rodape {{
    background: {p.superficie};
    border-top: 1px solid {sombra_linha};
}}
#rodapeTexto {{ color: {suave}; font-size: 8pt; }}
QStatusBar {{ background: {p.superficie}; color: {suave}; border-top: 1px solid {sombra_linha}; }}
QStatusBar QLabel {{ color: {suave}; background: transparent; }}
/* Rolagem: o fundo é da loja, NUNCA o do tema do sistema. Com o Windows em
   modo escuro o `QScrollArea` transparente deixava o preto do sistema aparecer
   atrás dos cartões, e o texto do rodapé/cabeçalho de seção ficava ilegível. */
QScrollArea {{ border: none; background: {p.fundo}; }}
QScrollArea > QWidget > QWidget {{ background: {p.fundo}; }}
QAbstractScrollArea::corner {{ background: {p.fundo}; }}
#pagina, #paginaRolavel {{ background: {p.fundo}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {_misturar(p.borda, "#000000", 0.12)};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {suave}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {_misturar(p.borda, "#000000", 0.12)};
    border-radius: 5px;
    min-width: 28px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QToolTip {{
    background: {p.primaria_escura};
    color: {branco};
    border: none;
    padding: 5px 7px;
    font-size: 8.5pt;
}}

/* ---------- diálogo de login ---------- */
#cartaoLogin {{
    background: {p.superficie};
    border: 1px solid {sombra_linha};
    border-radius: 6px;
}}
QScrollArea#rolagemDialogo, QScrollArea#rolagemDialogo > QWidget > QWidget {{
    background: transparent;
    border: none;
}}

/* A faixa virou um bloco (logo + título) na v0.11.0: o fundo da primária fica no
   bloco e o texto recebe a tinta por regra própria, porque folha não herda cor. */
#loginMarca {{
    background: {p.primaria};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 12px 16px;
}}
#loginMarcaTitulo {{
    background: transparent;
    color: {texto_botao};
    font-size: 13pt;
    font-weight: 700;
}}
#loginMarcaLogo, #logoOficial {{ background: transparent; }}
#loginSubtitulo {{ color: {suave}; font-size: 8.5pt; }}
"""


def tinta_do_botao(widget: object) -> str:
    """Cor de texto/ícone legível sobre a cor primária, na paleta em vigor.

    O ícone do botão principal era branco fixo: com uma marca de primária clara
    (rosa claro, areia, cinza) ele sumia no fundo — o mesmo defeito que a faixa do
    título do login tinha. `QPalette.Highlight` guarda a primária da loja e
    `WindowText` o texto; a escolha é por razão de contraste (WCAG).
    """
    from PySide6.QtGui import QPalette

    from ..dominio.marca import tinta_sobre

    paleta = widget.palette()  # type: ignore[attr-defined]
    primaria = paleta.color(QPalette.ColorRole.Highlight).name().upper()
    texto = paleta.color(QPalette.ColorRole.WindowText).name().upper()
    return tinta_sobre(primaria, escura=texto)


def folha_estilo_da_marca(marca: Marca) -> str:
    return folha_estilo(marca.paleta, marca.fonte)


def paleta_do_tema(paleta: Paleta | None = None) -> QPalette:
    """`QPalette` clara derivada da marca, para o que o QSS não pinta.

    O Qt 6.5+ segue o tema do Windows: com o sistema em modo escuro, a paleta
    padrão vem escura e todo widget sem regra de folha de estilo (páginas dentro
    do `QScrollArea`, fundo de diálogos, menus de combo, *placeholder* de campo)
    ficava preto com texto escuro — ilegível. Fixar a paleta aqui mantém a
    interface previsível em qualquer tema do sistema, e a cor continua sendo dado
    (vem de `Marca`).
    """
    from PySide6.QtGui import QColor, QPalette

    p = paleta or Paleta()
    q = QPalette()
    papel = QPalette.ColorRole
    grupo = QPalette.ColorGroup
    for ativo in (grupo.Active, grupo.Inactive):
        q.setColor(ativo, papel.Window, QColor(p.fundo))
        q.setColor(ativo, papel.WindowText, QColor(p.texto))
        q.setColor(ativo, papel.Base, QColor(p.superficie))
        q.setColor(ativo, papel.AlternateBase, QColor(_misturar(p.fundo, "#000000", 0.02)))
        q.setColor(ativo, papel.Text, QColor(p.texto))
        q.setColor(ativo, papel.Button, QColor(p.superficie))
        q.setColor(ativo, papel.ButtonText, QColor(p.texto))
        q.setColor(ativo, papel.BrightText, QColor("#FFFFFF"))
        q.setColor(ativo, papel.Highlight, QColor(p.primaria))
        q.setColor(ativo, papel.HighlightedText, QColor("#FFFFFF"))
        q.setColor(ativo, papel.ToolTipBase, QColor(p.primaria_escura))
        q.setColor(ativo, papel.ToolTipText, QColor("#FFFFFF"))
        q.setColor(ativo, papel.PlaceholderText, QColor(garantir_contraste(p.texto_suave, p.superficie)))
        q.setColor(ativo, papel.Light, QColor(p.superficie))
        q.setColor(ativo, papel.Midlight, QColor(p.fundo))
        q.setColor(ativo, papel.Mid, QColor(p.borda))
        q.setColor(ativo, papel.Dark, QColor(_misturar(p.borda, "#000000", 0.25)))
        q.setColor(ativo, papel.Shadow, QColor("#000000"))
        q.setColor(ativo, papel.Link, QColor(p.primaria))
        q.setColor(ativo, papel.LinkVisited, QColor(p.primaria_escura))
    # Desabilitado: texto suave e fundo neutro, mas ainda legível (≥ 4.5:1).
    q.setColor(grupo.Disabled, papel.Window, QColor(p.fundo))
    q.setColor(grupo.Disabled, papel.WindowText, QColor(garantir_contraste(p.texto_suave, p.fundo)))
    q.setColor(grupo.Disabled, papel.Base, QColor(p.superficie))
    q.setColor(grupo.Disabled, papel.Text, QColor(garantir_contraste(p.texto_suave, p.superficie)))
    q.setColor(grupo.Disabled, papel.Button, QColor(p.fundo))
    q.setColor(grupo.Disabled, papel.ButtonText, QColor(garantir_contraste(p.texto_suave, p.fundo)))
    return q


#: Compatibilidade: folha padrão calculada uma vez.
FOLHA_ESTILO = folha_estilo()
