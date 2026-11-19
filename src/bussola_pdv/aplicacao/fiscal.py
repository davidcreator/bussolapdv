"""Ponto de construção fiscal: contrato do emissor, desligado por decisão.

O programa **não emite documento fiscal** nesta fase (uso interno de bazar de
ONG, ADR-029). Este módulo existe para que a emissão, quando for decidida, entre
por uma porta só — sem espalhar `if fiscal` pela venda, pelo cupom e pelo
relatório.

O que está pronto: o contrato (`EmissorFiscal`), o documento (`DocumentoFiscal`),
a configuração lida dos parâmetros e um emissor que **recusa com mensagem clara**
em vez de fingir que emitiu. O que falta está em docs/FISCAL.md, item por item:
certificado, CSC, autorizador da UF, contingência, DANFE e homologação.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from ..dominio.erros import ErroBussola
from .contexto import Contexto

AVISO_FISCAL = (
    "Este documento é controle interno: não é documento fiscal e não substitui "
    "a nota fiscal exigida por lei."
)


class FiscalIndisponivel(ErroBussola):
    """A emissão fiscal não está configurada nesta instalação."""


class SituacaoFiscal(StrEnum):
    DESATIVADO = "DESATIVADO"
    EM_HOMOLOGACAO = "EM_HOMOLOGACAO"
    AUTORIZADO = "AUTORIZADO"
    REJEITADO = "REJEITADO"
    CONTINGENCIA = "CONTINGENCIA"
    CANCELADO = "CANCELADO"


class ModeloFiscal(StrEnum):
    """Modelos que a fazenda aceita para varejo."""

    NFC_E = "65"  # cupom fiscal eletrônico (o caso do PDV)
    NF_E = "55"  # nota fiscal eletrônica (venda com transporte/empresa)


@dataclass(frozen=True, slots=True)
class DocumentoFiscal:
    """O que um emissor precisa devolver — independente de provedor."""

    modelo: ModeloFiscal
    serie: int
    numero: int
    chave: str
    situacao: SituacaoFiscal
    emitido_em: datetime
    protocolo: str = ""
    xml: str = ""
    danfe_pdf: bytes | None = None
    mensagem_sefaz: str = ""
    avisos: tuple[str, ...] = (AVISO_FISCAL,)


@dataclass(frozen=True, slots=True)
class ConfiguracaoFiscal:
    """Lida dos parâmetros; tudo vazio = fiscal desligado (estado desta versão)."""

    habilitado: bool = False
    ambiente: str = "HOMOLOGACAO"
    uf: str = ""
    cnpj: str = ""
    regime: str = ""
    serie_nfce: int = 1
    certificado_caminho: str = ""
    csc_id: str = ""
    csc_disponivel: bool = False

    @property
    def situacao(self) -> SituacaoFiscal:
        if not self.habilitado:
            return SituacaoFiscal.DESATIVADO
        if self.ambiente.upper() == "HOMOLOGACAO":
            return SituacaoFiscal.EM_HOMOLOGACAO
        return SituacaoFiscal.AUTORIZADO

    def pendencias(self) -> tuple[str, ...]:
        """O que ainda falta para poder emitir — a lista que a tela vai mostrar."""
        faltando: list[str] = []
        if not self.habilitado:
            faltando.append("Emissão fiscal desligada por decisão do projeto (ADR-029).")
        if not self.uf:
            faltando.append("UF da loja (define o autorizador da SEFAZ).")
        if not self.cnpj:
            faltando.append("CNPJ do emitente.")
        if not self.certificado_caminho:
            faltando.append("Certificado digital A1 (.pfx) instalado na máquina.")
        if not self.csc_id or not self.csc_disponivel:
            faltando.append("CSC e ID do token do emitente (obtidos no portal da SEFAZ).")
        return tuple(faltando)


@runtime_checkable
class EmissorFiscal(Protocol):
    """Um provedor de emissão (SEFAZ direto, gateway, contingência)."""

    def emitir(self, venda_id: str) -> DocumentoFiscal: ...

    def cancelar(self, chave: str, motivo: str) -> DocumentoFiscal: ...

    def consultar(self, chave: str) -> DocumentoFiscal: ...


@dataclass
class EmissorFiscalDesativado:
    """Emissor padrão: recusa com o motivo, nunca inventa um documento."""

    configuracao: ConfiguracaoFiscal = field(default_factory=ConfiguracaoFiscal)

    def emitir(self, venda_id: str) -> DocumentoFiscal:
        raise FiscalIndisponivel(self._mensagem("emitir", venda_id))

    def cancelar(self, chave: str, motivo: str) -> DocumentoFiscal:
        raise FiscalIndisponivel(self._mensagem("cancelar", chave))

    def consultar(self, chave: str) -> DocumentoFiscal:
        raise FiscalIndisponivel(self._mensagem("consultar", chave))

    def _mensagem(self, acao: str, referencia: str) -> str:
        pendencias = self.configuracao.pendencias()
        lista = "; ".join(pendencias) if pendencias else "configuração incompleta"
        return (
            f"Não é possível {acao} documento fiscal para {referencia}: a emissão está "
            f"desligada nesta versão. Faltam: {lista}. Roteiro em docs/FISCAL.md. "
            f"{AVISO_FISCAL}"
        )


def configuracao_fiscal(contexto: Contexto) -> ConfiguracaoFiscal:
    """Lê o que existir de parâmetro fiscal; ausência não quebra a operação."""

    def ler(chave: str, padrao: str = "") -> str:
        try:
            return str(contexto.parametros.obter(chave))
        except ErroBussola:
            return padrao

    return ConfiguracaoFiscal(
        habilitado=ler("fiscal.habilitado", "0").strip() in {"1", "SIM", "true"},
        ambiente=ler("fiscal.ambiente", "HOMOLOGACAO"),
        uf=ler("fiscal.uf"),
        cnpj=ler("empresa.cnpj"),
        regime=ler("empresa.regime_tributario"),
        serie_nfce=int(ler("fiscal.serie_nfce", "1") or 1),
        certificado_caminho=ler("fiscal.certificado"),
        csc_id=ler("fiscal.csc_id"),
        csc_disponivel=ler("fiscal.csc_token", "").strip() != "",
    )


def emissor_fiscal(contexto: Contexto) -> EmissorFiscal:
    """Fábrica. Hoje devolve sempre o emissor desligado — de propósito."""
    return EmissorFiscalDesativado(configuracao_fiscal(contexto))


__all__ = [
    "AVISO_FISCAL",
    "ConfiguracaoFiscal",
    "DocumentoFiscal",
    "EmissorFiscal",
    "EmissorFiscalDesativado",
    "FiscalIndisponivel",
    "ModeloFiscal",
    "SituacaoFiscal",
    "configuracao_fiscal",
    "emissor_fiscal",
]
