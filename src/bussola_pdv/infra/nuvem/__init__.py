"""Armazenamento em nuvem: contrato único e **dois clientes reais** sem SDK.

v0.14.0: o contrato deixou de ser só esqueleto. `ArmazenamentoS3` e
`ArmazenamentoAzureBlob` fazem `PUT`/`GET`/`DELETE`/listagem de verdade, assinando
as requisições em biblioteca padrão (`infra/nuvem/assinatura.py` — SigV4 e Shared
Key, conferidos contra os exemplos publicados dos fornecedores).

Por que sem SDK: o programa instala no Windows com Python do sistema; cada
dependência nova é download, versão e suporte a mais. As duas assinaturas são
HMAC-SHA256 — cabem em `hmac`/`hashlib`.

O que continua fora do programa: a **credencial**. Chave de nuvem mora em variável
de ambiente da máquina (`BUSSOLA_AWS_ACCESS_KEY_ID`,
`BUSSOLA_AWS_SECRET_ACCESS_KEY`, `BUSSOLA_AZURE_CONTA`, `BUSSOLA_AZURE_CHAVE`),
nunca no banco do PDV nem no repositório. Sem elas, o cliente recusa na construção
com mensagem que diz o que falta — não tenta falar com a nuvem.

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
    variavel_acesso: str = ""  # S3: nome da env var com a chave de acesso (key id)
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


def criar_armazenamento(
    configuracao: ConfiguracaoNuvem, *, ambiente: dict[str, str] | None = None
) -> ArmazenamentoNuvem:
    """Fábrica: cliente do provedor escolhido, ou erro dizendo o que falta na credencial.

    `ambiente` existe para o teste injetar credenciais falsas sem mexer no processo.
    O import é tardio para que `import bussola_pdv.infra.nuvem` não puxe `urllib`.
    """
    from .azure import ArmazenamentoAzureBlob
    from .s3 import ArmazenamentoS3

    if configuracao.provedor == "S3":
        return ArmazenamentoS3(configuracao, ambiente=ambiente)
    if configuracao.provedor == "AZURE_BLOB":
        return ArmazenamentoAzureBlob(configuracao, ambiente=ambiente)
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
    "ArmazenamentoMemoria",
    "ArmazenamentoNuvem",
    "ConfiguracaoNuvem",
    "ErroNuvem",
    "NuvemNaoConfigurada",
    "criar_armazenamento",
    "enviar_backup",
]
