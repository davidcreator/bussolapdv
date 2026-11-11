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

from ..dominio.marca import FONTE_PADRAO, Marca, Paleta

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
    texto_botao = branco if p.contraste_branco_primaria >= 3.0 else p.texto
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
    color: {p.texto_suave};
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
    color: {p.texto_suave};
    font-size: 8.5pt;
}}
#trilhaConteudo {{
    color: {p.texto_suave};
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
    color: {p.texto_suave};
    font-size: 8pt;
}}
#tituloSecao {{
    color: {p.texto_suave};
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
    color: {p.texto_suave};
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
    color: {p.texto_suave};
    font-size: 7.5pt;
    font-weight: 700;
}}
#caixaInfoValor {{
    color: {p.texto};
    font-size: 16pt;
    font-weight: 700;
}}
#caixaInfoLegenda {{
    color: {p.texto_suave};
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
    color: {p.texto_suave};
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
    color: {p.texto_suave};
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
    color: {p.texto_suave};
}}
QComboBox {{ padding-right: 20px; }}
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
    color: {p.texto_suave};
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
    color: {p.texto_suave};
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
#textoAjuda {{ color: {p.texto_suave}; font-size: 8.5pt; }}
#destaqueAdmin {{ color: {p.primaria}; font-weight: 700; font-size: 12pt; }}

/* ---------- rodapé, status e diversos ---------- */
#rodape {{
    background: {p.superficie};
    border-top: 1px solid {sombra_linha};
}}
#rodapeTexto {{ color: {p.texto_suave}; font-size: 8pt; }}
QStatusBar {{ background: {p.superficie}; color: {p.texto_suave}; border-top: 1px solid {sombra_linha}; }}
QStatusBar QLabel {{ color: {p.texto_suave}; background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {_misturar(p.borda, "#000000", 0.12)};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.texto_suave}; }}
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
#loginMarca {{
    background: {p.primaria};
    color: {branco};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 16px;
    font-size: 13pt;
    font-weight: 700;
}}
#loginSubtitulo {{ color: {p.texto_suave}; font-size: 8.5pt; }}
"""


def folha_estilo_da_marca(marca: Marca) -> str:
    return folha_estilo(marca.paleta, marca.fonte)


#: Compatibilidade: folha padrão calculada uma vez.
FOLHA_ESTILO = folha_estilo()
