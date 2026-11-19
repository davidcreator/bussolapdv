"""Certificado autoassinado gerado pelo próprio programa (ADR-035).

O certificado é produzido por código DER escrito à mão, sem `cryptography` e sem `openssl`
instalado. Isso significa que um erro de um byte gera um arquivo que "parece" um certificado e
que nenhum navegador aceita — por isso o teste não confia no arquivo: **reparseia o DER** aqui e
confere a assinatura RSA matematicamente (`pow(s, e, n)` com PKCS#1 v1.5), além de exigir que a
biblioteca padrão (`ssl`) carregue o par como servidor TLS de verdade.

O que este arquivo guarda, e por quê:

1. serial **positivo** — série negativa é recusada por validador estrito (já aconteceu aqui);
2. `Name` com RDN em **SET (0x31)** — com SEQUENCE o OpenSSL só diz "PEM lib";
3. SAN com `localhost` e os IPs, senão o terminal recusa o servidor pelo nome;
4. impressão digital estável e no formato que se lê por telefone;
5. `obter_ou_criar` **reaproveita**: gerar de novo a cada subida trocaria a digital e obrigaria a
   reconfigurar todos os caixas;
6. chave privada com permissão 0600 fora do Windows.
"""

from __future__ import annotations

import hashlib
import os
import ssl
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bussola_pdv.infra.rede.certificado import (
    BITS_PADRAO,
    CertificadoServidor,
    ErroCertificado,
    criar_certificado,
    der_inteiro,
    der_sequencia,
    der_set,
    impressao_digital,
    ler_certificado,
    obter_ou_criar,
)

# -- leitor DER mínimo --------------------------------------------------------

OID_SHA256_RSA = bytes.fromhex("2a864886f70d01010b")
DIGEST_INFO_SHA256 = bytes.fromhex("3031300d060960864801650304020105000420")


class Elemento:
    """Um elemento DER com as duas faixas que interessam: TLV inteiro e conteúdo."""

    __slots__ = ("der", "fim", "inicio", "inicio_tlv", "tag")

    def __init__(self, der: bytes, tag: int, inicio_tlv: int, inicio: int, fim: int) -> None:
        self.der = der
        self.tag = tag
        self.inicio_tlv = inicio_tlv
        self.inicio = inicio
        self.fim = fim

    @property
    def conteudo(self) -> bytes:
        return self.der[self.inicio : self.fim]

    @property
    def cru(self) -> bytes:
        """O TLV com cabeçalho — é o que a assinatura cobre, byte a byte."""
        return self.der[self.inicio_tlv : self.fim]

    def filhos(self) -> list[Elemento]:
        return _filhos(self.der, self.inicio, self.fim)


def _ler(der: bytes, posicao: int = 0) -> Elemento:
    inicio_tlv = posicao
    tag = der[posicao]
    posicao += 1
    primeiro = der[posicao]
    posicao += 1
    if primeiro < 0x80:
        tamanho = primeiro
    else:
        quantidade = primeiro & 0x7F
        tamanho = int.from_bytes(der[posicao : posicao + quantidade], "big")
        posicao += quantidade
    return Elemento(der, tag, inicio_tlv, posicao, posicao + tamanho)


def _filhos(der: bytes, inicio: int, fim: int) -> list[Elemento]:
    saida: list[Elemento] = []
    posicao = inicio
    while posicao < fim:
        elemento = _ler(der, posicao)
        saida.append(elemento)
        posicao = elemento.fim
    return saida


class CertificadoLido:
    """O certificado relido do disco, campo por campo."""

    def __init__(self, der: bytes) -> None:
        self.der = der
        externo = _ler(der, 0)
        assert externo.tag == 0x30
        partes = externo.filhos()
        assert len(partes) == 3, "certificado deve ter tbs, algoritmo e assinatura"
        self.tbs, self.assinatura_algoritmo, self.assinatura = partes
        campos = self.tbs.filhos()
        self.versao = campos[0]
        self.serie = campos[1]
        self.algoritmo = campos[2]
        self.emissor = campos[3]
        self.validade = campos[4]
        self.titular = campos[5]
        self.chave_publica = campos[6]
        self.extensoes = campos[7] if len(campos) > 7 else None

    @property
    def serie_bytes(self) -> bytes:
        assert self.serie.tag == 0x02
        return self.serie.conteudo

    @property
    def tbs_bytes(self) -> bytes:
        return self.tbs.cru

    @property
    def assinatura_bytes(self) -> bytes:
        assert self.assinatura.tag == 0x03
        conteudo = self.assinatura.conteudo
        assert conteudo[0] == 0, "BIT STRING da assinatura não deve ter bits de padding"
        return conteudo[1:]

    @property
    def chave_publica_rsa(self) -> tuple[int, int]:
        # SubjectPublicKeyInfo = SEQUENCE { SEQUENCE { algoritmo }, BIT STRING { RSAPublicKey } }
        assert self.chave_publica.tag == 0x30
        algoritmo, bits = self.chave_publica.filhos()
        assert algoritmo.tag == 0x30
        assert bits.tag == 0x03
        conteudo = bits.conteudo
        assert conteudo[0] == 0, "BIT STRING da chave não deve ter bits de padding"
        spki = _ler(conteudo[1:], 0)
        assert spki.tag == 0x30
        modulo, expoente = spki.filhos()
        return (
            int.from_bytes(modulo.conteudo, "big"),
            int.from_bytes(expoente.conteudo, "big"),
        )

    @property
    def datas(self) -> tuple[datetime, datetime]:
        assert self.validade.tag == 0x30
        antes, depois = self.validade.filhos()
        return (_tempo_do(antes), _tempo_do(depois))

    @property
    def nomes_san(self) -> list[str]:
        """Nomes do `subjectAltName` (2.5.29.17), lidos direto das extensões."""
        assert self.extensoes is not None
        assert self.extensoes.tag == 0xA3
        lista = _ler(self.extensoes.conteudo, 0)
        assert lista.tag == 0x30
        saida: list[str] = []
        for extensao in lista.filhos():
            oid, valor = extensao.filhos()[:2]
            if oid.conteudo != bytes.fromhex("551d11"):  # 2.5.29.17
                continue
            interno = _ler(valor.conteudo, 0)  # OCTET STRING com a SEQUENCE
            assert interno.tag == 0x30
            for nome in interno.filhos():
                if nome.tag == 0x82:  # dNSName
                    saida.append(nome.conteudo.decode("ascii"))
                elif nome.tag == 0x87:  # iPAddress
                    saida.append(".".join(str(parte) for parte in nome.conteudo))
        return saida


def _tempo_do(elemento: Elemento) -> datetime:
    cru = elemento.conteudo.decode("ascii")
    formato = "%Y%m%d%H%M%SZ" if elemento.tag == 0x18 else "%y%m%d%H%M%SZ"
    return datetime.strptime(cru, formato).replace(tzinfo=UTC)


def _ler_certificado(arquivo: Path) -> CertificadoLido:
    der = ssl.PEM_cert_to_DER_cert(arquivo.read_text(encoding="ascii"))
    return CertificadoLido(der)


# -- fixtures ----------------------------------------------------------------


@pytest.fixture(scope="module")
def certificado(tmp_path_factory: pytest.TempPathFactory) -> CertificadoServidor:
    return criar_certificado(tmp_path_factory.mktemp("tls"), nome="Bussola Teste")


# -- DER: as três armadilhas que já custaram tempo ---------------------------


class TestCodificacaoDer:
    def test_inteiro_positivo_ganha_byte_de_sinal(self) -> None:
        # 0x80 sozinho é -128 em DER; o correto é 00 80.
        assert der_inteiro(0x80) == b"\x02\x02\x00\x80"
        assert der_inteiro(0) == b"\x02\x01\x00"
        assert der_inteiro(1) == b"\x02\x01\x01"

    def test_rdn_e_SET_e_nao_SEQUENCE(self) -> None:
        # Com SEQUENCE o OpenSSL recusa o PEM com "PEM lib" e não diz o motivo.
        assert der_set(b"\x02\x01\x01")[0] == 0x31
        assert der_sequencia(b"\x02\x01\x01")[0] == 0x30

    def test_tamanho_longo_usa_forma_estendida(self) -> None:
        corpo = b"\x00" * 300
        codificado = der_sequencia(corpo)
        assert codificado[0] == 0x30
        assert codificado[1] == 0x82
        assert codificado[2:4] == (300).to_bytes(2, "big")
        assert codificado[4:] == corpo


# -- estrutura do certificado ------------------------------------------------


class TestEstrutura:
    def test_pem_legivel_e_der_canonico(self, certificado: CertificadoServidor) -> None:
        texto = certificado.certificado.read_text(encoding="ascii")
        assert texto.startswith("-----BEGIN CERTIFICATE-----")
        assert texto.rstrip().endswith("-----END CERTIFICATE-----")
        lido = _ler_certificado(certificado.certificado)
        # SEQUENCE externa com tamanho declarado igual ao arquivo: não sobrou nem faltou byte
        externo = _ler(lido.der, 0)
        assert externo.tag == 0x30
        assert externo.fim == len(lido.der)

    def test_versao_v3(self, certificado: CertificadoServidor) -> None:
        lido = _ler_certificado(certificado.certificado)
        assert lido.versao.cru == b"\xa0\x03\x02\x01\x02", "version deve ser v3 (valor 2)"

    def test_serie_positiva_e_diferente_por_certificado(
        self, certificado: CertificadoServidor, tmp_path: Path
    ) -> None:
        lido = _ler_certificado(certificado.certificado)
        serie = lido.serie_bytes
        assert serie, "série vazia não é aceita"
        assert serie[0] & 0x80 == 0, "série negativa é recusada por validador estrito"
        assert int.from_bytes(serie, "big") > 0
        outro = criar_certificado(tmp_path / "outro", nome="Bussola Teste")
        assert _ler_certificado(outro.certificado).serie_bytes != serie

    def test_emissor_e_titular_em_SET(self, certificado: CertificadoServidor) -> None:
        lido = _ler_certificado(certificado.certificado)
        for nome in (lido.emissor, lido.titular):
            assert nome.tag == 0x30, "Name é SEQUENCE"
            primeiro = nome.filhos()[0]
            assert primeiro.tag == 0x31, "RDN tem de ser SET (0x31), não SEQUENCE"

    def test_validade_de_dez_anos(self, certificado: CertificadoServidor) -> None:
        inicio, fim = _ler_certificado(certificado.certificado).datas
        dias = (fim - inicio).days
        assert 365 * 10 - 2 <= dias <= 365 * 10 + 2

    def test_algoritmo_e_sha256_com_rsa(self, certificado: CertificadoServidor) -> None:
        lido = _ler_certificado(certificado.certificado)
        oid = lido.assinatura_algoritmo.filhos()[0]
        assert oid.conteudo == OID_SHA256_RSA

    def test_chave_de_2048_bits(self, certificado: CertificadoServidor) -> None:
        modulo, expoente = _ler_certificado(certificado.certificado).chave_publica_rsa
        assert modulo.bit_length() == BITS_PADRAO
        assert expoente == 65537

    def test_san_tem_localhost_e_ip(self, certificado: CertificadoServidor) -> None:
        nomes = _ler_certificado(certificado.certificado).nomes_san
        assert "localhost" in nomes
        assert "127.0.0.1" in nomes
        assert all(":" not in nome or "." not in nome for nome in nomes)

    def test_assinatura_rsa_confere_matematicamente(
        self, certificado: CertificadoServidor
    ) -> None:
        lido = _ler_certificado(certificado.certificado)
        modulo, expoente = lido.chave_publica_rsa
        tamanho = (modulo.bit_length() + 7) // 8
        assinatura = int.from_bytes(lido.assinatura_bytes, "big")
        recuperado = pow(assinatura, expoente, modulo).to_bytes(tamanho, "big")
        digest = hashlib.sha256(lido.tbs_bytes).digest()
        esperado = (
            b"\x00\x01"
            + b"\xff" * (tamanho - 3 - len(DIGEST_INFO_SHA256) - len(digest))
            + b"\x00"
            + DIGEST_INFO_SHA256
            + digest
        )
        assert recuperado == esperado, "assinatura não cobre o tbsCertificate"


# -- uso real: TLS -----------------------------------------------------------


class TestUsoComoServidorTls:
    def test_contexto_carrega_certificado_e_chave(self, certificado: CertificadoServidor) -> None:
        contexto = certificado.contexto_tls()
        assert isinstance(contexto, ssl.SSLContext)
        assert contexto.minimum_version >= ssl.TLSVersion.TLSv1_2

    def test_chave_privada_tem_permissao_restrita(self, certificado: CertificadoServidor) -> None:
        if sys.platform == "win32":  # pragma: no cover - chmod é limitado no Windows
            pytest.skip("permissão POSIX não se aplica ao Windows")
        modo = stat.S_IMODE(os.stat(certificado.chave).st_mode)
        assert modo == 0o600

    def test_chave_e_privada_em_pem(self, certificado: CertificadoServidor) -> None:
        texto = certificado.chave.read_text(encoding="ascii")
        assert texto.startswith("-----BEGIN RSA PRIVATE KEY-----")
        assert "PUBLIC KEY" not in texto


# -- impressão digital e reaproveitamento ------------------------------------


class TestImpressaoDigital:
    def test_formato_de_conferencia_por_telefone(self, certificado: CertificadoServidor) -> None:
        pares = certificado.digital.split(":")
        assert len(pares) == 32
        assert all(len(par) == 2 and par == par.upper() for par in pares)
        assert certificado.digital == impressao_digital(
            ssl.PEM_cert_to_DER_cert(certificado.certificado.read_text(encoding="ascii"))
        )

    def test_ler_certificado_devolve_a_mesma_digital(self, certificado: CertificadoServidor) -> None:
        relido = ler_certificado(certificado.certificado)
        assert relido.digital == certificado.digital
        assert relido.chave == certificado.chave

    def test_obter_ou_criar_reaproveita(self, tmp_path: Path) -> None:
        pasta = tmp_path / "tls"
        primeiro = obter_ou_criar(pasta, nome="Bussola Reuso")
        carimbo = primeiro.certificado.stat().st_mtime_ns
        segundo = obter_ou_criar(pasta, nome="Bussola Reuso")
        assert segundo.certificado == primeiro.certificado
        assert segundo.digital == primeiro.digital
        assert segundo.certificado.stat().st_mtime_ns == carimbo, "certificado foi regerado"

    def test_criar_com_enderecos_proprios(self, tmp_path: Path) -> None:
        gerado = criar_certificado(tmp_path / "tls", enderecos_ip=["192.168.0.10"])
        nomes = _ler_certificado(gerado.certificado).nomes_san
        assert "192.168.0.10" in nomes
        assert "192.168.0.10" in gerado.nomes

    def test_agora_controla_a_validade(self, tmp_path: Path) -> None:
        agora = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
        gerado = criar_certificado(tmp_path / "tls", agora=agora)
        inicio, fim = _ler_certificado(gerado.certificado).datas
        assert inicio <= agora <= fim
        assert fim - agora >= timedelta(days=365 * 9)


class TestErros:
    def test_certificado_ausente_levanta_erro(self, tmp_path: Path) -> None:
        with pytest.raises(ErroCertificado):
            ler_certificado(tmp_path / "servidor.crt")

    def test_chave_ausente_levanta_erro(self, tmp_path: Path, certificado: CertificadoServidor) -> None:
        copia = tmp_path / "servidor.crt"
        copia.write_text(certificado.certificado.read_text(encoding="ascii"), encoding="ascii")
        with pytest.raises(ErroCertificado):
            ler_certificado(copia)
