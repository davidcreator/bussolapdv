"""Folha de estilo gerada a partir da paleta da loja.

A paleta deixou de ser constante: ela vem de `Marca` (tabela `parametros`), é
validada no domínio e interpolada aqui. Contraste e foco visível continuam sendo
requisitos de acessibilidade, não enfeite — a cor nunca é o único indicador, e
paletas com contraste abaixo de 4,5:1 geram aviso na tela de tema.
"""

from __future__ import annotations

from ..dominio.marca import FONTE_PADRAO, Marca, Paleta

#: Paleta padrão exposta como constantes para telas e testes que precisam de cor solta.
_PADRAO = Paleta()
GRAFITE = _PADRAO.primaria
GRAFITE_ESCURO = _PADRAO.primaria_escura
TURQUESA = _PADRAO.secundaria
TURQUESA_CLARA = _PADRAO.secundaria_clara
AMBAR = _PADRAO.destaque
ENTRADA = _PADRAO.entrada
CALCULADA = "#F2F2F2"
TEXTO = _PADRAO.texto
TEXTO_SUAVE = _PADRAO.texto_suave
SUCESSO = _PADRAO.sucesso
ALERTA = _PADRAO.alerta
ERRO = _PADRAO.erro
BORDA = _PADRAO.borda

FONTE = FONTE_PADRAO


def _misturar(cor: str, outra: str = "#FFFFFF", fator: float = 0.15) -> str:
    """Mistura dois hexadecimais (usado para estados hover, sem tabela de cores)."""
    canais = []
    for inicio in (1, 3, 5):
        a = int(cor[inicio : inicio + 2], 16)
        b = int(outra[inicio : inicio + 2], 16)
        canais.append(round(a + (b - a) * fator))
    return "#" + "".join(f"{canal:02X}" for canal in canais)


def folha_estilo(paleta: Paleta | None = None, fonte: str | None = None) -> str:
    """QSS completo. Recebe paleta e fonte já validadas pelo domínio."""
    p = paleta or Paleta()
    familia = fonte or FONTE_PADRAO
    hover_primaria = _misturar(p.primaria, "#FFFFFF", 0.12)
    hover_navegacao = _misturar(p.primaria_escura, "#FFFFFF", 0.10)
    calculada = _misturar(p.fundo, "#000000", 0.06)
    texto_botao = "#FFFFFF" if p.contraste_branco_primaria >= 3.0 else p.texto
    return f"""
QWidget {{
    font-family: "{familia}", "DejaVu Sans", sans-serif;
    font-size: 10pt;
    color: {p.texto};
    background: {p.superficie};
}}
QMainWindow, QDialog {{ background: {p.fundo}; }}

#faixaSuperior {{
    background: {p.primaria};
    color: #FFFFFF;
    padding: 10px 16px;
}}
#faixaSuperior QLabel {{ color: #FFFFFF; background: transparent; }}
#tituloApp {{ font-size: 15pt; font-weight: 600; }}
#subtituloApp {{ color: {p.secundaria_clara}; font-size: 9pt; }}

#faixaSecundaria {{
    background: {p.secundaria};
    color: #FFFFFF;
    padding: 6px 16px;
}}
#faixaSecundaria QLabel {{ color: #FFFFFF; font-weight: 600; background: transparent; }}

#navegacao {{
    background: {p.primaria_escura};
    color: #FFFFFF;
    border: none;
    outline: none;
}}
#navegacao::item {{ padding: 10px 14px; }}
#navegacao::item:selected {{ background: {p.secundaria}; color: #FFFFFF; }}
#navegacao::item:hover {{ background: {hover_navegacao}; }}

QGroupBox {{
    border: 1px solid {p.borda};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {p.primaria};
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit, QTextEdit {{
    background: {p.entrada};
    border: 1px solid {p.destaque};
    border-radius: 4px;
    padding: 5px 7px;
    selection-background-color: {p.secundaria};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px solid {p.secundaria};
}}
QLineEdit:read-only, QLineEdit[calculado="true"] {{
    background: {calculada};
    border: 1px solid {p.borda};
}}
QLineEdit:disabled {{ background: {calculada}; color: {p.texto_suave}; }}

QPushButton {{
    background: {p.primaria};
    color: {texto_botao};
    border: none;
    border-radius: 4px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {hover_primaria}; }}
QPushButton:focus {{ outline: 2px solid {p.destaque}; }}
QPushButton:disabled {{ background: {p.borda}; color: {p.texto_suave}; }}
QPushButton#secundario {{ background: {calculada}; color: {p.primaria}; }}
QPushButton#secundario:hover {{ background: {p.borda}; }}
QPushButton#perigo {{ background: {p.erro}; color: #FFFFFF; }}

QTableWidget, QTableView, QTreeWidget {{
    background: {p.superficie};
    alternate-background-color: {calculada};
    gridline-color: {p.borda};
    selection-background-color: {p.secundaria_clara};
    selection-color: {p.texto};
}}
QHeaderView::section {{
    background: {p.primaria};
    color: {texto_botao};
    padding: 6px;
    border: none;
    font-weight: 600;
}}
QTabWidget::pane {{ border: 1px solid {p.borda}; }}
QCheckBox, QRadioButton {{ background: transparent; }}

#totalCupom {{
    font-size: 22pt;
    font-weight: 700;
    color: {p.primaria};
    background: {calculada};
    border-radius: 6px;
    padding: 8px;
}}
#mensagemOk {{ color: {p.sucesso}; font-weight: 600; }}
#mensagemAlerta {{ color: {p.alerta}; font-weight: 600; }}
#mensagemErro {{ color: {p.erro}; font-weight: 600; }}
#textoAjuda {{ color: {p.texto_suave}; font-size: 9pt; }}
#destaqueAdmin {{ color: {p.primaria}; font-weight: 700; font-size: 12pt; }}
QStatusBar {{ background: {p.primaria_escura}; color: #FFFFFF; }}
QStatusBar QLabel {{ color: #FFFFFF; background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: {p.primaria}; color: #FFFFFF; border: none; padding: 5px; }}
"""


def folha_estilo_da_marca(marca: Marca) -> str:
    return folha_estilo(marca.paleta, marca.fonte)


#: Compatibilidade: folha padrão calculada uma vez.
FOLHA_ESTILO = folha_estilo()
