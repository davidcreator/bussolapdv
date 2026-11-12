"""Marca da loja e paleta de cores: identidade visual configurável e auditável.

Duas regras guiam este módulo:

* **Cor é dado, não código.** A paleta vive no banco (`parametros`), é validada
  como hexadecimal e vira folha de estilo em tempo de execução.
* **Contraste não é gosto.** Toda paleta é avaliada pela razão de contraste
  WCAG entre texto e superfície; abaixo de 4,5:1 o sistema avisa que a
  legibilidade (e portanto a operação) está comprometida.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from .erros import ErroValidacao

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_NOME_VALIDO = re.compile(r"^[A-Za-zÀ-ÿ0-9 .,'&()/-]{1,60}$")
_FONTE_VALIDA = re.compile(r"^[A-Za-z0-9 \-]{1,40}$")
_LOGO_LIMITE_BYTES = 200_000

PREFIXO = "marca."
PREFIXO_TEMA = "marca.tema."  # subprefixo: uma leitura só (marca.*) traz tudo


def _cor(nome: str, valor: str) -> str:
    if not _HEX.match(valor):
        raise ErroValidacao(f"Cor inválida em {nome}: {valor!r} (use #RRGGBB).")
    return valor.upper()


def _luminancia(hexadecimal: str) -> float:
    """Luminância relativa conforme WCAG 2.1."""
    componentes = []
    for inicio in (1, 3, 5):
        canal = int(hexadecimal[inicio : inicio + 2], 16) / 255
        componentes.append(canal / 12.92 if canal <= 0.03928 else ((canal + 0.055) / 1.055) ** 2.4)
    vermelho, verde, azul = componentes
    return 0.2126 * vermelho + 0.7152 * verde + 0.0722 * azul


def razao_contraste(cor_a: str, cor_b: str) -> float:
    """Razão de contraste WCAG entre duas cores hex."""
    brilho_a, brilho_b = sorted((_luminancia(cor_a), _luminancia(cor_b)), reverse=True)
    return round((brilho_a + 0.05) / (brilho_b + 0.05), 2)


def tinta_sobre(fundo: str, *, clara: str = "#FFFFFF", escura: str = "#1F1F1F") -> str:
    """Cor de texto legível sobre `fundo`: a de maior contraste, não a "mais bonita".

    A heurística antiga era luminosidade média (`lightnessF() > 0.6`), que erra
    justamente nas tintas em que a leitura falha: no amarelo de destaque
    `#FFC107` ela escolhia texto branco — 1,63:1, praticamente invisível. Aqui a
    decisão é a razão de contraste WCAG.
    """
    return clara if razao_contraste(clara, fundo) >= razao_contraste(escura, fundo) else escura


def garantir_contraste(cor: str, fundo: str, *, alvo: float = 4.5, passos: int = 20) -> str:
    """Escurece (fundo claro) ou clareia (fundo escuro) `cor` até passar de `alvo`.

    Serve para o texto secundário de uma loja que escolheu um cinza claro demais:
    em vez de exibir ajuda e rodapé ilegíveis, a interface aproxima a tinta do
    preto (ou do branco) o mínimo necessário — e só o mínimo, para não perder a
    hierarquia visual.
    """
    if razao_contraste(cor, fundo) >= alvo:
        return cor
    destino = "#000000" if _luminancia(fundo) > 0.5 else "#FFFFFF"
    for passo in range(1, passos + 1):
        candidata = _misturar_hex(cor, destino, passo / passos)
        if razao_contraste(candidata, fundo) >= alvo:
            return candidata
    return destino


def _misturar_hex(cor: str, outra: str, fator: float) -> str:
    canais = []
    for inicio in (1, 3, 5):
        a = int(cor[inicio : inicio + 2], 16)
        b = int(outra[inicio : inicio + 2], 16)
        canais.append(round(a + (b - a) * fator))
    return "#" + "".join(f"{canal:02X}" for canal in canais)


@dataclass(frozen=True, slots=True)
class Paleta:
    """Cores da interface. Nomes funcionais, não nomes de tinta."""

    # Skin padrão inspirada no AdminLTE/Bootstrap 5: azul de ação, sidebar grafite,
    # fundo cinza-azulado e cartões brancos. Nomes funcionais, não nomes de tinta.
    primaria: str = "#0D6EFD"
    primaria_escura: str = "#343A40"
    secundaria: str = "#17A2B8"
    secundaria_clara: str = "#D3E9F0"
    destaque: str = "#FFC107"
    fundo: str = "#F4F6F9"
    superficie: str = "#FFFFFF"
    texto: str = "#212529"
    # Cinza do Bootstrap 5 escurecido: o #6C757D original dá 4,33:1 sobre o fundo
    # #F4F6F9 — abaixo de WCAG AA (4,5:1) para texto pequeno, que é onde ele é
    # usado (ajuda, rodapé, descrição de seção). Ver `garantir_contraste`.
    texto_suave: str = "#5F686F"
    sucesso: str = "#198754"
    alerta: str = "#856404"
    erro: str = "#B02A37"
    borda: str = "#DEE2E6"
    entrada: str = "#FFFFFF"

    def __post_init__(self) -> None:
        for nome in self.__slots__:
            object.__setattr__(self, nome, _cor(nome, getattr(self, nome)))

    def com(self, **cores: str) -> Paleta:
        return replace(self, **cores)

    @property
    def contraste_texto_superficie(self) -> float:
        return razao_contraste(self.texto, self.superficie)

    @property
    def contraste_branco_primaria(self) -> float:
        return razao_contraste("#FFFFFF", self.primaria)

    def avisos(self) -> list[str]:
        mensagens: list[str] = []
        if self.contraste_texto_superficie < 4.5:
            mensagens.append(
                f"Contraste texto/superfície de {self.contraste_texto_superficie}:1 "
                "está abaixo do mínimo de 4,5:1."
            )
        if self.contraste_branco_primaria < 3.0:
            mensagens.append(
                f"Contraste branco/primária de {self.contraste_branco_primaria}:1 "
                "deixa títulos e cabeçalhos ilegíveis."
            )
        # O texto secundário aparece sobre o fundo da janela (ajuda, rodapé,
        # descrição de seção) e sobre os cartões brancos. WCAG AA pede 4,5:1 nos
        # dois: a interface corrige automaticamente, mas a loja precisa saber.
        if razao_contraste(self.texto_suave, self.fundo) < 4.5:
            mensagens.append(
                f"Texto secundário sobre o fundo: "
                f"{razao_contraste(self.texto_suave, self.fundo)}:1 "
                "(a interface escurece até 4,5:1)."
            )
        if razao_contraste(self.texto_suave, self.superficie) < 3.0:
            mensagens.append("Texto suave com contraste baixo; ajuda e rodapés ficarão ilegíveis.")
        if razao_contraste(self.destaque, self.superficie) < 1.4:
            mensagens.append("Cor de destaque quase invisível sobre a superfície.")
        return mensagens

    def a_dicionario(self) -> dict[str, str]:
        return {nome: getattr(self, nome) for nome in self.__slots__}

    @classmethod
    def de_dicionario(cls, valores: Mapping[str, str]) -> Paleta:
        conhecidas = {nome: valores[nome] for nome in cls.__slots__ if nome in valores}
        return replace(cls(), **conhecidas)


#: Paletas prontas. O nome é o que o lojista vê no seletor de tema.
PALETAS_PADRAO: dict[str, Paleta] = {
    "BUSSOLA": Paleta(),
    "GRAFITE": Paleta(
        primaria="#495057",
        primaria_escura="#212529",
        secundaria="#6C757D",
        secundaria_clara="#E9ECEF",
        destaque="#E0A800",
        fundo="#F1F3F5",
        superficie="#FFFFFF",
        texto="#212529",
        texto_suave="#6C757D",
        sucesso="#1E7B34",
        alerta="#8A5A00",
        erro="#B3261E",
        borda="#CED4DA",
        entrada="#FFFFFF",
    ),
    "ESMERALDA": Paleta(
        primaria="#0F7B57",
        primaria_escura="#1E3B31",
        secundaria="#20C997",
        secundaria_clara="#D6F2E9",
        destaque="#F2B705",
        fundo="#F2F7F5",
        superficie="#FFFFFF",
        texto="#14251E",
        texto_suave="#4F6157",
        sucesso="#0F7B3F",
        alerta="#7A5200",
        erro="#A4262C",
        borda="#CDDED6",
        entrada="#FFFFFF",
    ),
    "NOTURNO": Paleta(
        primaria="#3D8BFD",
        primaria_escura="#141A21",
        secundaria="#4DB8C4",
        secundaria_clara="#22303C",
        destaque="#F6C445",
        fundo="#0F141A",
        superficie="#1A222C",
        texto="#E8EEF5",
        texto_suave="#A9B7C6",
        sucesso="#3FB950",
        alerta="#D29922",
        erro="#F85149",
        borda="#303C4A",
        entrada="#222D3A",
    ),
    "OCEANO": Paleta(
        primaria="#0B7285",
        primaria_escura="#17323A",
        secundaria="#22B8CF",
        secundaria_clara="#D3EFF3",
        destaque="#FFC107",
        fundo="#F3F7F8",
        superficie="#FFFFFF",
        texto="#1B2A2E",
        texto_suave="#5C7076",
        sucesso="#198754",
        alerta="#856404",
        erro="#B02A37",
        borda="#D8E2E5",
        entrada="#FFFFFF",
    ),
}

PRESET_PADRAO = "BUSSOLA"
PRESET_PERSONALIZADO = "PERSONALIZADO"
PRESETS_VALIDOS = frozenset({*PALETAS_PADRAO, PRESET_PERSONALIZADO})
FONTE_PADRAO = "Segoe UI"


@dataclass(frozen=True, slots=True)
class Marca:
    """Identidade da loja: nome, dados de contato, logo e paleta."""

    nome_fantasia: str = "Loja de Demonstração"
    razao_social: str = ""
    cnpj: str = ""
    telefone: str = ""
    endereco: str = ""
    rodape_comprovante: str = "Obrigado pela preferência! Documento interno, não fiscal."
    preset: str = PRESET_PADRAO
    paleta: Paleta = field(default_factory=Paleta)
    fonte: str = FONTE_PADRAO
    logo_data_uri: str = ""

    def __post_init__(self) -> None:
        nome = self.nome_fantasia.strip()
        if not nome:
            raise ErroValidacao("O nome da loja é obrigatório.")
        if not _NOME_VALIDO.match(nome):
            raise ErroValidacao(
                "Nome da loja aceita letras, números, espaços e . , ' & ( ) / - (até 60 caracteres)."
            )
        object.__setattr__(self, "nome_fantasia", nome)
        if not _FONTE_VALIDA.match(self.fonte):
            raise ErroValidacao("Fonte inválida: use apenas letras, números, espaço e hífen.")
        if self.preset not in PRESETS_VALIDOS:
            raise ErroValidacao(f"Preset de tema desconhecido: {self.preset}")
        if self.logo_data_uri:
            self._validar_logo(self.logo_data_uri)
        for campo in ("razao_social", "telefone", "endereco", "rodape_comprovante"):
            if len(getattr(self, campo)) > 200:
                raise ErroValidacao(f"{campo.replace('_', ' ').capitalize()} excede 200 caracteres.")

    @staticmethod
    def _validar_logo(valor: str) -> None:
        if not valor.startswith("data:image/png;base64,"):
            raise ErroValidacao("O logo deve ser PNG embutido (data:image/png;base64,...).")
        try:
            conteudo = base64.b64decode(valor.split(",", 1)[1], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ErroValidacao("Logo em base64 inválido.") from exc
        if len(conteudo) > _LOGO_LIMITE_BYTES:
            raise ErroValidacao(
                f"Logo acima de {_LOGO_LIMITE_BYTES // 1000} KB; reduza a imagem."
            )
        if not conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ErroValidacao("O arquivo enviado não é um PNG válido.")

    @property
    def avisos(self) -> list[str]:
        return self.paleta.avisos()

    def com(self, **mudancas: object) -> Marca:
        return replace(self, **mudancas)  # type: ignore[arg-type]

    def com_preset(self, preset: str) -> Marca:
        if preset not in PALETAS_PADRAO:
            raise ErroValidacao(f"Preset de tema desconhecido: {preset}")
        return replace(self, preset=preset, paleta=PALETAS_PADRAO[preset])

    def com_cores(self, **cores: str) -> Marca:
        """Personalização livre: mantém o resto e passa a ser 'PERSONALIZADO'."""
        return replace(
            self, preset=PRESET_PERSONALIZADO, paleta=self.paleta.com(**cores)
        )

    def a_parametros(self) -> dict[str, str]:
        """Formato persistido: tudo texto, chaves estáveis, sem tipo composto."""
        valores = {
            f"{PREFIXO}nome_fantasia": self.nome_fantasia,
            f"{PREFIXO}razao_social": self.razao_social,
            f"{PREFIXO}cnpj": self.cnpj,
            f"{PREFIXO}telefone": self.telefone,
            f"{PREFIXO}endereco": self.endereco,
            f"{PREFIXO}rodape_comprovante": self.rodape_comprovante,
            f"{PREFIXO}fonte": self.fonte,
            f"{PREFIXO}logo_data_uri": self.logo_data_uri,
            f"{PREFIXO}preset": self.preset,
        }
        for nome, valor in self.paleta.a_dicionario().items():
            valores[f"{PREFIXO_TEMA}{nome}"] = valor
        return valores

    @classmethod
    def de_parametros(cls, valores: Mapping[str, str]) -> Marca:
        """Constrói a marca a partir do dicionário de parâmetros, sem confiar nele."""
        base = cls()
        preset = valores.get(f"{PREFIXO}preset", base.preset) or base.preset
        if preset not in PRESETS_VALIDOS:
            preset = PRESET_PADRAO
        paleta_base = PALETAS_PADRAO.get(preset, base.paleta)
        cores = {}
        for nome in Paleta.__slots__:
            bruto = valores.get(f"{PREFIXO_TEMA}{nome}", "")
            if bruto and _HEX.match(bruto):
                cores[nome] = bruto
        dados = {
            "nome_fantasia": valores.get(f"{PREFIXO}nome_fantasia", base.nome_fantasia),
            "razao_social": valores.get(f"{PREFIXO}razao_social", ""),
            "cnpj": valores.get(f"{PREFIXO}cnpj", ""),
            "telefone": valores.get(f"{PREFIXO}telefone", ""),
            "endereco": valores.get(f"{PREFIXO}endereco", ""),
            "rodape_comprovante": valores.get(
                f"{PREFIXO}rodape_comprovante", base.rodape_comprovante
            ),
            "fonte": valores.get(f"{PREFIXO}fonte", FONTE_PADRAO) or FONTE_PADRAO,
            "logo_data_uri": valores.get(f"{PREFIXO}logo_data_uri", ""),
            "preset": preset,
            "paleta": replace(paleta_base, **cores),
        }
        try:
            return cls(**dados)  # type: ignore[arg-type]
        except ErroValidacao:
            # Dado corrompido no banco não pode impedir a abertura do PDV.
            return base

    @classmethod
    def padrao(cls) -> Marca:
        return cls()

    def resumo(self) -> str:
        return f"{self.nome_fantasia} · tema {self.preset}"
