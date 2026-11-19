"""Configuração do caixa terminal e o certificado que ele confia (ADR-036).

O arquivo é pequeno e legível de propósito — quem cuida do computador da loja
precisa poder abrir, ler e apagar. Ele guarda:

* **endereço** do servidor (https://maquina-da-loja:8765);
* **token da API** (o que autoriza *este programa* a falar com o servidor);
* **nome do terminal** (`CAIXA-02`), que vai em cada venda e no log;
* **impressão digital** do certificado confirmada pelo operador no primeiro uso.

O certificado em si fica ao lado, como PEM. Ele funciona como a única
autoridade aceita: o `ssl` do Python recusa qualquer outro servidor, mesmo que
alguém consiga um certificado "válido" na rede da loja. Não é confiança em
"qualquer autoridade do planeta", é confiança **neste** servidor — o que é
exatamente o que uma rede local precisa.

Sem este arquivo, o programa abre em modo local (base na própria máquina). O
modo remoto nunca é presumido.
"""

from __future__ import annotations

import json
import ssl
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

NOME_DO_ARQUIVO = "terminal.json"
NOME_DO_CERTIFICADO = "servidor-do-caixa.crt"


class ErroDeConfiguracao(RuntimeError):
    """Configuração ausente, ilegível ou incompleta."""


@dataclass(frozen=True, slots=True)
class ConfiguracaoRemota:
    endereco: str
    token: str
    terminal: str = "CAIXA-01"
    digital: str = ""
    certificado: str = NOME_DO_CERTIFICADO

    def __post_init__(self) -> None:
        endereco = self.endereco.strip().rstrip("/")
        if not endereco:
            raise ErroDeConfiguracao("Informe o endereço do servidor.")
        if "://" not in endereco:
            endereco = f"https://{endereco}"
        partes = urlparse(endereco)
        if partes.scheme not in {"http", "https"} or not partes.hostname:
            raise ErroDeConfiguracao(f"Endereço inválido: {self.endereco!r}.")
        if len(self.token) < 16:
            raise ErroDeConfiguracao("O token da API precisa de pelo menos 16 caracteres.")
        if not self.terminal.strip():
            raise ErroDeConfiguracao("Informe o nome deste caixa (ex.: CAIXA-02).")
        object.__setattr__(self, "endereco", endereco)

    @property
    def seguro(self) -> bool:
        return urlparse(self.endereco).scheme == "https"

    @property
    def base(self) -> str:
        return f"{self.endereco}/v1"

    def arquivo_do_certificado(self, pasta: Path) -> Path:
        return Path(pasta) / self.certificado

    def contexto_tls(self, pasta: Path) -> ssl.SSLContext:
        """Contexto que só confia no certificado guardado deste servidor.

        `check_hostname=False` é deliberado: o certificado é autoassinado e o
        operador pode ter digitado o IP em vez do nome da máquina. A garantia real
        vem do arquivo de certificado — ele é a **única** raiz aceita.
        """
        arquivo = self.arquivo_do_certificado(pasta)
        if not arquivo.is_file():
            raise ErroDeConfiguracao(
                f"Certificado do servidor ausente em {arquivo}. Configure este caixa de novo."
            )
        contexto = ssl.create_default_context(cafile=str(arquivo))
        contexto.check_hostname = False
        contexto.minimum_version = ssl.TLSVersion.TLSv1_2
        return contexto

    def para_json(self) -> dict:
        return asdict(self)


def pasta_de_configuracao(pasta_de_dados: Path) -> Path:
    return Path(pasta_de_dados)


def carregar(pasta: Path) -> ConfiguracaoRemota | None:
    """Devolve a configuração salva, ou `None` se este caixa está em modo local."""
    arquivo = Path(pasta) / NOME_DO_ARQUIVO
    if not arquivo.is_file():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ErroDeConfiguracao(
            f"Não consegui ler {arquivo}: {exc}. Apague o arquivo para voltar ao modo local."
        ) from exc
    if not isinstance(dados, dict):
        raise ErroDeConfiguracao(f"{arquivo} não contém um objeto JSON.")
    try:
        return ConfiguracaoRemota(
            endereco=str(dados.get("endereco", "")),
            token=str(dados.get("token", "")),
            terminal=str(dados.get("terminal") or "CAIXA-01"),
            digital=str(dados.get("digital", "")),
            certificado=str(dados.get("certificado") or NOME_DO_CERTIFICADO),
        )
    except ErroDeConfiguracao as exc:
        raise ErroDeConfiguracao(f"{arquivo}: {exc}") from exc


def salvar(pasta: Path, configuracao: ConfiguracaoRemota) -> Path:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / NOME_DO_ARQUIVO
    arquivo.write_text(
        json.dumps(configuracao.para_json(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return arquivo


def remover(pasta: Path) -> bool:
    """Volta o computador ao modo local (base própria)."""
    arquivo = Path(pasta) / NOME_DO_ARQUIVO
    if not arquivo.is_file():
        return False
    arquivo.unlink()
    return True


def guardar_certificado(pasta: Path, der: bytes, *, configuracao: ConfiguracaoRemota) -> Path:
    """Grava o certificado confirmado pelo operador como única raiz aceita."""
    import base64

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    corpo = base64.encodebytes(der).decode("ascii").replace("\n", "")
    linhas = [corpo[inicio : inicio + 64] for inicio in range(0, len(corpo), 64)]
    destino = configuracao.arquivo_do_certificado(pasta)
    destino.write_text(
        "-----BEGIN CERTIFICATE-----\n"
        + "\n".join(linhas)
        + "\n-----END CERTIFICATE-----\n",
        encoding="ascii",
    )
    return destino


@dataclass(frozen=True, slots=True)
class InspecaoDeCertificado:
    """O que o primeiro uso mostra ao operador antes de confiar."""

    digital: str
    der: bytes = field(repr=False)
    valido_ate: str = ""
    nomes: tuple[str, ...] = ()


__all__ = [
    "NOME_DO_ARQUIVO",
    "NOME_DO_CERTIFICADO",
    "ConfiguracaoRemota",
    "ErroDeConfiguracao",
    "InspecaoDeCertificado",
    "carregar",
    "guardar_certificado",
    "pasta_de_configuracao",
    "remover",
    "salvar",
]
