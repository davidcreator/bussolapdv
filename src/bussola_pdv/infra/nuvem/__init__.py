"""Armazenamento em nuvem: contrato único para AWS S3 e Azure Blob — **base**.

O que está pronto nesta versão é o **contrato** e a configuração: qualquer código
que precise guardar um arquivo (backup, exportação, anexo) fala com
`ArmazenamentoNuvem`, e o provedor entra depois. Cadastrar credencial de nuvem
nesta entrega seria prometer o que não foi homologado — quando a loja decidir,
basta instalar o SDK (`boto3` ou `azure-storage-blob`) e implementar os quatro
métodos; nada mais no programa muda.

Por que assim: o programa é offline por decisão (ADR-029 mantém "nada de rede" no
dia a dia). Nuvem aqui é **destino de cópia de segurança** e, no futuro, o
servidor central do multi-caixa — não dependência do caixa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ...dominio.erros import ErroBussola


class NuvemNaoConfigurada(ErroBussola):
    """O provedor foi escolhido, mas o cliente/SDK não está disponível."""


class ErroNuvem(ErroBussola):
    """Falha ao falar com o provedor (credencial, rede, permissão)."""


@dataclass(frozen=True, slots=True)
class ConfiguracaoNuvem:
    """O que é preciso para apontar para um balde/contêiner.

    Nada de segredo aqui dentro além do nome da variável de ambiente: senha e
    chave **nunca** ficam no repositório nem no banco do PDV.
    """

    provedor: str  # "S3" | "AZURE_BLOB"
    recipiente: str  # bucket (S3) ou container (Azure)
    regiao: str = ""
    prefixo: str = "bussolapdv/"
    conta: str = ""  # Azure: nome da conta de armazenamento
    variavel_chave: str = ""  # nome da env var com a chave/secreta
    endpoint: str = ""  # S3-compatível (MinIO, Wasabi, R2)
    criptografia: str = "AES256"  # SSE-S3 por padrão

    def __post_init__(self) -> None:
        if self.provedor not in PROVEDORES:
            raise ErroNuvem(
                f"Provedor desconhecido: {self.provedor!r}. Use um de {', '.join(PROVEDORES)}."
            )
        if not self.recipiente.strip():
            raise ErroNuvem("Informe o balde (S3) ou contêiner (Azure).")

    @property
    def rotulo(self) -> str:
        return f"{self.provedor}:{self.recipiente}"


PROVEDORES: tuple[str, ...] = ("S3", "AZURE_BLOB")

#: O que a loja precisa decidir antes de ligar a nuvem (documentado em docs/NUVEM.md).
REQUISITOS: tuple[tuple[str, str], ...] = (
    ("Conta", "AWS: conta + usuário IAM só com permissão no balde. Azure: conta de armazenamento."),
    ("Recipiente", "Um balde/contêiner por instalação, na região mais próxima (ex.: sa-east-1)."),
    ("Credencial", "Chave em variável de ambiente da máquina; nunca no banco nem no código."),
    ("Criptografia", "SSE no provedor + backup já manifestado com sha256 pelo programa."),
    ("Retenção", "Regra de ciclo de vida: 30 dias na nuvem, 14 cópias locais."),
    ("LGPD", "Dado pessoal em nuvem exige base legal e prazo de guarda (pendência P6)."),
    ("Custo", "Alguns reais por mês para o volume do bazar — mas é decisão de quem paga."),
)


@runtime_checkable
class ArmazenamentoNuvem(Protocol):
    """Quatro operações bastam para backup e exportação."""

    def enviar(self, caminho: Path, *, nome: str | None = None) -> str: ...

    def baixar(self, nome: str, destino: Path) -> Path: ...

    def listar(self) -> list[str]: ...

    def remover(self, nome: str) -> None: ...


class _BaseNaoConfigurada:
    """Esqueleto compartilhado: falha com mensagem útil, nunca em silêncio."""

    def __init__(self, configuracao: ConfiguracaoNuvem) -> None:
        self.configuracao = configuracao

    def _erro(self) -> NuvemNaoConfigurada:
        return NuvemNaoConfigurada(
            f"{self.configuracao.rotulo}: cliente do provedor não instalado nesta versão. "
            "O contrato está pronto (docs/NUVEM.md) — falta instalar o SDK e implementar "
            "enviar/baixar/listar/remover."
        )

    def enviar(self, caminho: Path, *, nome: str | None = None) -> str:
        raise self._erro()

    def baixar(self, nome: str, destino: Path) -> Path:
        raise self._erro()

    def listar(self) -> list[str]:
        raise self._erro()

    def remover(self, nome: str) -> None:
        raise self._erro()


class ArmazenamentoS3(_BaseNaoConfigurada):
    """AWS S3 (ou S3-compatível: MinIO, Wasabi, Cloudflare R2)."""


class ArmazenamentoAzureBlob(_BaseNaoConfigurada):
    """Azure Blob Storage."""


@dataclass
class ArmazenamentoMemoria:
    """Implementação de teste: guarda em dicionário, prova o contrato sem rede."""

    configuracao: ConfiguracaoNuvem = field(
        default_factory=lambda: ConfiguracaoNuvem(provedor="S3", recipiente="teste")
    )
    arquivos: dict[str, bytes] = field(default_factory=dict)
    enviados: list[str] = field(default_factory=list)

    def enviar(self, caminho: Path, *, nome: str | None = None) -> str:
        chave = self.configuracao.prefixo + (nome or Path(caminho).name)
        self.arquivos[chave] = Path(caminho).read_bytes()
        self.enviados.append(chave)
        return chave

    def baixar(self, nome: str, destino: Path) -> Path:
        if nome not in self.arquivos:
            raise ErroNuvem(f"Objeto inexistente: {nome}")
        destino = Path(destino)
        destino.write_bytes(self.arquivos[nome])
        return destino

    def listar(self) -> list[str]:
        return sorted(self.arquivos)

    def remover(self, nome: str) -> None:
        self.arquivos.pop(nome, None)


def criar_armazenamento(configuracao: ConfiguracaoNuvem) -> ArmazenamentoNuvem:
    """Fábrica: devolve o cliente do provedor escolhido (ainda não configurado)."""
    if configuracao.provedor == "S3":
        return ArmazenamentoS3(configuracao)
    if configuracao.provedor == "AZURE_BLOB":
        return ArmazenamentoAzureBlob(configuracao)
    raise ErroNuvem(f"Provedor não suportado: {configuracao.provedor}")


def enviar_backup(armazenamento: ArmazenamentoNuvem, caminho: Path) -> str:
    """Envia a cópia de segurança e devolve a chave criada no provedor."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroNuvem(f"Arquivo de backup inexistente: {caminho}")
    return armazenamento.enviar(caminho, nome=caminho.name)


__all__ = [
    "PROVEDORES",
    "REQUISITOS",
    "ArmazenamentoAzureBlob",
    "ArmazenamentoMemoria",
    "ArmazenamentoNuvem",
    "ArmazenamentoS3",
    "ConfiguracaoNuvem",
    "ErroNuvem",
    "NuvemNaoConfigurada",
    "criar_armazenamento",
    "enviar_backup",
]
