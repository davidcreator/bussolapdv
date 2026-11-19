"""Certificado TLS autoassinado gerado pelo próprio programa, sem `openssl` nem SDK.

Por que isto existe: o modo servidor de vários caixas precisa de TLS (o token e a
senha do operador não podem viajar em claro na rede da loja), mas pedir ao dono do
bazar que instale OpenSSL ou compre certificado é receita para "deixa sem TLS".
Então o programa gera a chave RSA e o certificado X.509 na primeira vez que sobe em
modo servidor, com `secrets`, `hashlib` e um codificador DER de ~100 linhas.

O que este certificado é e o que **não** é:

* é **autoassinado** — o terminal precisa confiar nele uma vez (o programa mostra a
  impressão digital SHA-256 para conferir por telefone, o mesmo procedimento dos
  administradores de rede);
* **não** substitui certificado público: não serve para acesso pela internet, só
  para a rede local (SAN com o IP da máquina, `localhost` e o nome do servidor);
* a chave privada fica no disco com permissão restrita ao usuário que roda o
  servidor, nunca no banco nem no repositório.

Custo: gerar 2048 bits em Python puro leva ~1 s; acontece uma vez, no primeiro
`bussola api --tls`, e fica guardado.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import secrets
import socket
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

BITS_PADRAO = 2048
_E_PUBLICO = 65537
_VALIDADE_ANOS = 10

# OIDs que entram no certificado (RFC 5280 / PKCS#1).
_OID_RSA = bytes.fromhex("2a864886f70d010101")  # 1.2.840.113549.1.1.1
_OID_SHA256_RSA = bytes.fromhex("2a864886f70d01010b")  # 1.2.840.113549.1.1.11
_OID_CN = bytes.fromhex("550403")  # 2.5.4.3
_OID_BASIC = bytes.fromhex("551d13")  # 2.5.29.19
_OID_KEY_USAGE = bytes.fromhex("551d0f")  # 2.5.29.15
_OID_EXT_KEY_USAGE = bytes.fromhex("551d25")  # 2.5.29.37
_OID_SAN = bytes.fromhex("551d11")  # 2.5.29.17
_OID_SERVER_AUTH = bytes.fromhex("2b06010505070301")  # 1.3.6.1.5.5.7.3.1


class ErroCertificado(RuntimeError):
    """Não foi possível gerar ou ler o certificado do servidor."""


# ------------------------------------------------------------------ DER básico
def _tamanho(tamanho: int) -> bytes:
    if tamanho < 0x80:
        return bytes([tamanho])
    corpo = tamanho.to_bytes((tamanho.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(corpo)]) + corpo


def _tlv(tag: int, conteudo: bytes) -> bytes:
    return bytes([tag]) + _tamanho(len(conteudo)) + conteudo


def der_set(conteudo: bytes) -> bytes:
    return _tlv(0x31, conteudo)


def der_sequencia(*partes: bytes) -> bytes:
    return _tlv(0x30, b"".join(partes))


def der_inteiro(valor: int) -> bytes:
    """Inteiro DER canônico: mínimo de bytes e **positivo** (bit alto exige `00` na frente)."""
    if valor == 0:
        return _tlv(0x02, b"\x00")
    corpo = valor.to_bytes((valor.bit_length() + 7) // 8, "big")
    if corpo[0] & 0x80:  # sem isto o número vira negativo (-128 em vez de 128)
        corpo = b"\x00" + corpo
    return _tlv(0x02, corpo)


def der_oid(oid: bytes) -> bytes:
    return _tlv(0x06, oid)


def der_nulo() -> bytes:
    return b"\x05\x00"


def der_texto(rotulo: str) -> bytes:
    return _tlv(0x0C, rotulo.encode("utf-8"))  # UTF8String


def der_bits(dados: bytes, *, bits_de_padding: int = 0) -> bytes:
    return _tlv(0x03, bytes([bits_de_padding]) + dados)


def der_octetos(dados: bytes) -> bytes:
    return _tlv(0x04, dados)


def der_booleano(valor: bool) -> bytes:
    return _tlv(0x01, b"\xff" if valor else b"\x00")


def der_tempo(momento: datetime) -> bytes:
    return _tlv(0x17, momento.strftime("%y%m%d%H%M%SZ").encode("ascii"))  # UTCTime


# ------------------------------------------------------------------- chave RSA
def _primo(bits: int) -> int:
    """Primo aleatório de `bits`, filtrado por primos pequenos antes do Miller-Rabin."""
    pequenos = (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)
    while True:
        candidato = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if any(candidato % primo == 0 for primo in pequenos):
            continue
        if _teste_miller_rabin(candidato, rodadas=32):
            return candidato


def _teste_miller_rabin(numero: int, *, rodadas: int) -> bool:
    if numero in (2, 3):
        return True
    if numero < 2 or numero % 2 == 0:
        return False
    resto, expoente = numero - 1, 0
    while resto % 2 == 0:
        resto //= 2
        expoente += 1
    for _ in range(rodadas):
        base = secrets.randbelow(numero - 3) + 2
        valor = pow(base, resto, numero)
        if valor in (1, numero - 1):
            continue
        for _ in range(expoente - 1):
            valor = pow(valor, 2, numero)
            if valor == numero - 1:
                break
        else:
            return False
    return True


@dataclass(frozen=True, slots=True)
class _ChaveRSA:
    n: int
    e: int
    d: int
    p: int
    q: int

    @property
    def bits(self) -> int:
        return self.n.bit_length()

    def assinar(self, mensagem: bytes) -> bytes:
        """PKCS#1 v1.5 com SHA-256 — o que o TLS com RSA espera."""
        resumo = hashlib.sha256(mensagem).digest()
        prefixo = bytes.fromhex("3031300d060960864801650304020105000420")
        preenchimento = self.bits // 8 - len(prefixo) - len(resumo) - 3
        if preenchimento < 8:
            raise ErroCertificado("Chave pequena demais para assinar com SHA-256.")
        bloco = b"\x00\x01" + b"\xff" * preenchimento + b"\x00" + prefixo + resumo
        return pow(int.from_bytes(bloco, "big"), self.d, self.n).to_bytes(self.bits // 8, "big")

    def privada_pem(self) -> str:
        """PKCS#1 (`BEGIN RSA PRIVATE KEY`), formato que o OpenSSL lê direto."""
        der = der_sequencia(
            der_inteiro(0),
            der_inteiro(self.n),
            der_inteiro(self.e),
            der_inteiro(self.d),
            der_inteiro(self.p),
            der_inteiro(self.q),
            der_inteiro(self.d % (self.p - 1)),
            der_inteiro(self.d % (self.q - 1)),
            der_inteiro(pow(self.q, -1, self.p)),
        )
        return _pem("RSA PRIVATE KEY", der)

    def publica_der(self) -> bytes:
        return der_sequencia(der_inteiro(self.n), der_inteiro(self.e))


def gerar_chave(bits: int = BITS_PADRAO) -> _ChaveRSA:
    ifbits = bits // 2
    while True:
        p = _primo(ifbits)
        q = _primo(bits - ifbits)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        fi = (p - 1) * (q - 1)
        if fi % _E_PUBLICO == 0:
            continue
        return _ChaveRSA(n=n, e=_E_PUBLICO, d=pow(_E_PUBLICO, -1, fi), p=p, q=q)


# ------------------------------------------------------------------ certificado
def _pem(rotulo: str, der: bytes) -> str:
    import base64

    corpo = base64.encodebytes(der).decode("ascii").replace("\n", "")
    linhas = [corpo[i : i + 64] for i in range(0, len(corpo), 64)]
    return f"-----BEGIN {rotulo}-----\n" + "\n".join(linhas) + f"\n-----END {rotulo}-----\n"


def _spki(chave: _ChaveRSA) -> bytes:
    return der_sequencia(
        der_sequencia(der_oid(_OID_RSA), der_nulo()),
        der_bits(chave.publica_der()),
    )


def _nome_comum(rotulo: str) -> bytes:
    # Name = SEQUENCE OF RelativeDistinguishedName, e cada RDN é um **SET** (0x31).
    # Trocar SET por SEQUENCE aqui gera DER que o OpenSSL recusa sem dizer por quê.
    atributo = der_sequencia(der_oid(_OID_CN), der_texto(rotulo))
    return der_sequencia(der_set(atributo))


def _extensoes(nomes_dns: list[str], enderecos_ip: list[str]) -> bytes:
    basic = der_sequencia(der_oid(_OID_BASIC), der_booleano(True), der_octetos(
        der_sequencia(der_booleano(True), der_inteiro(0))
    ))
    uso = der_sequencia(
        der_oid(_OID_KEY_USAGE),
        der_booleano(True),
        der_octetos(der_bits(b"\xa0", bits_de_padding=5)),  # digitalSignature+keyEncipherment
    )
    proposito = der_sequencia(
        der_oid(_OID_EXT_KEY_USAGE),
        der_octetos(der_sequencia(der_oid(_OID_SERVER_AUTH))),
    )
    alternativos = b""
    for nome in nomes_dns:
        alternativos += _tlv(0x82, nome.encode("ascii"))
    for endereco in enderecos_ip:
        alternativos += _tlv(0x87, socket.inet_aton(endereco))
    san = der_sequencia(der_oid(_OID_SAN), der_octetos(der_sequencia(alternativos)))
    return der_sequencia(basic, uso, proposito, san)


@dataclass(frozen=True, slots=True)
class CertificadoServidor:
    """Par certificado/chave gravado em disco, mais a impressão digital."""

    certificado: Path
    chave: Path
    digital: str  # SHA-256 do DER, em pares hexadecimais
    nomes: tuple[str, ...]

    def contexto_tls(self) -> ssl.SSLContext:

        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexto.minimum_version = ssl.TLSVersion.TLSv1_2
        contexto.load_cert_chain(certfile=str(self.certificado), keyfile=str(self.chave))
        return contexto


def ip_local() -> str:
    """IP da máquina na rede local (sem enviar pacote: o connect é UDP e não sai)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.connect(("10.255.255.255", 1))
            return str(sonda.getsockname()[0])
    except OSError:  # pragma: no cover - máquina sem rede
        return "127.0.0.1"


def criar_certificado(
    pasta: Path,
    *,
    nome: str | None = None,
    nomes_dns: list[str] | None = None,
    enderecos_ip: list[str] | None = None,
    bits: int = BITS_PADRAO,
    agora: datetime | None = None,
) -> CertificadoServidor:
    """Gera par chave/certificado autoassinado e grava em `pasta`."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    nome_comum = nome or f"Bussola PDV {socket.gethostname()}"
    agora = agora or datetime.now(UTC)
    chave = gerar_chave(bits)

    nomes = list(dict.fromkeys(nomes_dns or ["localhost", socket.gethostname()]))
    ips = list(dict.fromkeys(enderecos_ip or ["127.0.0.1", "::1", ip_local()]))
    ips = [ip for ip in ips if ":" not in ip]  # inet_aton só aceita IPv4

    tbs = der_sequencia(
        _tlv(0xA0, der_inteiro(2)),  # [0] version = v3
        # Série positiva: 119 bits garantem que o byte mais alto não acenda o bit de
        # sinal do inteiro DER (série negativa é recusada por validadores estritos).
        der_inteiro(secrets.randbits(119) | (1 << 118) | 1),
        der_sequencia(der_oid(_OID_SHA256_RSA), der_nulo()),
        _nome_comum(nome_comum),
        der_sequencia(
            der_tempo(agora - timedelta(days=1)),
            der_tempo(agora + timedelta(days=365 * _VALIDADE_ANOS)),
        ),
        _nome_comum(nome_comum),
        _spki(chave),
        _tlv(0xA3, _extensoes(nomes, ips)),
    )
    assinatura = chave.assinar(tbs)
    certificado_der = der_sequencia(
        tbs,
        der_sequencia(der_oid(_OID_SHA256_RSA), der_nulo()),
        der_bits(assinatura),
    )

    certificado = pasta / "servidor.crt"
    arquivo_chave = pasta / "servidor.key"
    certificado.write_text(_pem("CERTIFICATE", certificado_der), encoding="ascii")
    arquivo_chave.write_text(chave.privada_pem(), encoding="ascii")
    # No Windows o efeito do chmod é limitado, mas não atrapalha.
    with contextlib.suppress(OSError):
        os.chmod(arquivo_chave, 0o600)
    return CertificadoServidor(
        certificado=certificado,
        chave=arquivo_chave,
        digital=impressao_digital(certificado_der),
        nomes=tuple(nomes + ips),
    )


def impressao_digital(der: bytes) -> str:
    """SHA-256 em pares hexadecimais, como se lê em conferência por telefone."""
    cru = hashlib.sha256(der).hexdigest().upper()
    return ":".join(cru[i : i + 2] for i in range(0, len(cru), 2))


def ler_certificado(caminho: Path) -> CertificadoServidor:
    """Lê o par já gerado e devolve a impressão digital (sem reparsear ASN.1)."""
    import base64

    caminho = Path(caminho)
    chave = caminho.with_suffix(".key")
    if not caminho.is_file() or not chave.is_file():
        raise ErroCertificado(f"Certificado ou chave ausente em {caminho.parent}")
    corpo = "".join(
        linha
        for linha in caminho.read_text(encoding="ascii").splitlines()
        if not linha.startswith("-----")
    )
    der = base64.b64decode(corpo)
    return CertificadoServidor(
        certificado=caminho, chave=chave, digital=impressao_digital(der), nomes=()
    )


def obter_ou_criar(
    pasta: Path,
    *,
    nome: str | None = None,
    enderecos_ip: list[str] | None = None,
) -> CertificadoServidor:
    """Idempotente: reaproveita o certificado da instalação; cria no primeiro uso."""
    pasta = Path(pasta)
    existente = pasta / "servidor.crt"
    if existente.is_file() and (pasta / "servidor.key").is_file():
        return ler_certificado(existente)
    return criar_certificado(pasta, nome=nome, enderecos_ip=enderecos_ip)


__all__ = [
    "BITS_PADRAO",
    "CertificadoServidor",
    "ErroCertificado",
    "criar_certificado",
    "gerar_chave",
    "impressao_digital",
    "ip_local",
    "ler_certificado",
    "obter_ou_criar",
]
