"""Assinatura de nuvem e clientes S3/Azure — provados sem falar com a nuvem.

Três camadas de prova, de baixo para cima:

1. **Vetores publicados**: a assinatura SigV4 reproduz exatamente o `Authorization`
   do exemplo da AWS e o `StringToSign` do exemplo da Microsoft. Se a canonicalização
   quebrar, estes dois testes acusam antes de qualquer conta de nuvem existir.
2. **Ida e volta contra servidor falso**: um `HTTPServer` local faz o papel de S3 e
   de Azure Blob (aceita `PUT`, devolve `GET`, lista em XML) e confere que a
   requisição chegou assinada, com os cabeçalhos que cada provedor exige.
3. **Recusa de credencial**: sem variável de ambiente, o cliente não nasce — e a
   mensagem diz qual variável falta.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

from bussola_pdv.infra.nuvem import (
    ConfiguracaoNuvem,
    ErroNuvem,
    NuvemNaoConfigurada,
    criar_armazenamento,
    enviar_backup,
)
from bussola_pdv.infra.nuvem.assinatura import (
    assinar_shared_key,
    assinar_sigv4,
    consulta_canonica,
    data_azure,
    string_para_assinar_azure,
)

IDENTIDADE = datetime(2015, 8, 30, 12, 36, tzinfo=UTC)


# --------------------------------------------------------------- vetores oficiais
def test_sigv4_reproduz_o_exemplo_publicado_da_aws():
    """Exemplo da AWS: GET iam.amazonaws.com/?Action=ListUsers&Version=2010-05-08."""
    cabecalhos = assinar_sigv4(
        metodo="GET",
        host="iam.amazonaws.com",
        caminho="/",
        consulta={"Action": "ListUsers", "Version": "2010-05-08"},
        regiao="us-east-1",
        servico="iam",
        chave_acesso="AKIDEXAMPLE",
        chave_secreta="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
        momento=IDENTIDADE,
        cabecalhos={"content-type": "application/x-www-form-urlencoded; charset=utf-8"},
        assinar_hash_corpo=False,
    )
    assert cabecalhos["x-amz-date"] == "20150830T123600Z"
    assert cabecalhos["Authorization"] == (
        "AWS4-HMAC-SHA256 "
        "Credential=AKIDEXAMPLE/20150830/us-east-1/iam/aws4_request, "
        "SignedHeaders=content-type;host;x-amz-date, "
        "Signature=5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7"
    )


def test_string_para_assinar_do_azure_reproduz_o_exemplo_publicado():
    """Exemplo da Microsoft: Get Blob num contêiner com `comp`, `restype` e `timeout`."""
    string = string_para_assinar_azure(
        metodo="GET",
        conta="myaccount",
        caminho="/mycontainer",
        consulta={"comp": "metadata", "restype": "container", "timeout": "20"},
        data="Fri, 26 Jun 2015 23:39:12 GMT",
        cabecalhos_ms={"x-ms-version": "2015-02-21"},
    )
    assert string == (
        "GET\n\n\n\n\n\n\n\n\n\n\n\n"
        "x-ms-date:Fri, 26 Jun 2015 23:39:12 GMT\n"
        "x-ms-version:2015-02-21\n"
        "/myaccount/mycontainer\n"
        "comp:metadata\nrestype:container\ntimeout:20"
    )


def test_string_do_azure_usa_comprimento_vazio_quando_o_corpo_e_zero():
    string = string_para_assinar_azure(
        metodo="PUT", conta="conta", caminho="/c/b.db", content_length=0, data="x"
    )
    assert string.split("\n")[3] == ""  # Content-Length vazio, como manda a versão atual
    assert string_para_assinar_azure(
        metodo="PUT", conta="conta", caminho="/c/b.db", content_length=10, data="x"
    ).split("\n")[3] == "10"


def test_assinatura_shared_key_tem_o_formato_da_azure():
    import base64
    import hashlib
    import hmac

    chave = base64.b64encode(b"chave-de-teste").decode()
    cabecalho = assinar_shared_key(conta="loja", chave_base64=chave, string_para_assinar="GET\n\n")
    esperado = base64.b64encode(
        hmac.new(b"chave-de-teste", b"GET\n\n", hashlib.sha256).digest()
    ).decode()
    assert cabecalho == f"SharedKey loja:{esperado}"


def test_consulta_canonica_ordena_e_codifica():
    assert consulta_canonica({"b": "2", "a": "1 2"}) == "a=1%202&b=2"


def test_data_do_azure_esta_em_gmt():
    assert data_azure(IDENTIDADE) == "Sun, 30 Aug 2015 12:36:00 GMT"


# ---------------------------------------------------------- servidor falso local
class _FalsoNuvem(BaseHTTPRequestHandler):
    """Faz o papel de S3 e de Azure: guarda bytes, lista em XML, confere assinatura."""

    arquivos: ClassVar[dict[str, bytes]] = {}
    pedidos: ClassVar[list[dict]] = []
    modo: ClassVar[str] = "S3"

    def log_message(self, *args) -> None:  # silencia o log do http.server
        ...

    def _registrar(self) -> None:
        _FalsoNuvem.pedidos.append(
            {
                "metodo": self.command,
                "caminho": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "corpo": self.rfile.read(int(self.headers.get("Content-Length") or 0)),
            }
        )

    def _chave(self) -> str:
        return self.path.split("?")[0].lstrip("/")

    def _xml_lista(self) -> bytes:
        if _FalsoNuvem.modo == "S3":
            itens = "".join(f"<Contents><Key>{k}</Key></Contents>" for k in sorted(_FalsoNuvem.arquivos))
            corpo = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<ListBucketResult>{itens}</ListBucketResult>"
            )
        else:
            itens = "".join(
                f"<Blob><Name>{k}</Name></Blob>" for k in sorted(_FalsoNuvem.arquivos)
            )
            corpo = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<EnumerationResults><Blobs>{itens}</Blobs></EnumerationResults>"
            )
        return corpo.encode()

    def do_PUT(self) -> None:
        self._registrar()
        _FalsoNuvem.arquivos[self._chave()] = _FalsoNuvem.pedidos[-1]["corpo"]
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        self._registrar()
        chave = self._chave()
        if "?" in self.path or chave in {"", "balde", "backups"}:
            corpo = self._xml_lista()
        elif chave in _FalsoNuvem.arquivos:
            corpo = _FalsoNuvem.arquivos[chave]
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_DELETE(self) -> None:
        self._registrar()
        _FalsoNuvem.arquivos.pop(self._chave(), None)
        self.send_response(204)
        self.end_headers()


@pytest.fixture
def servidor_falso():
    _FalsoNuvem.arquivos = {}
    _FalsoNuvem.pedidos = []
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _FalsoNuvem)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    porta = servidor.server_address[1]
    yield f"http://127.0.0.1:{porta}"
    servidor.shutdown()
    servidor.server_close()


AMB_S3 = {
    "BUSSOLA_AWS_ACCESS_KEY_ID": "AKIDEXAMPLE",
    "BUSSOLA_AWS_SECRET_ACCESS_KEY": "segredo-de-teste",
}


class TestS3:
    def test_ida_e_volta_pelo_servidor_falso(self, servidor_falso, tmp_path):
        _FalsoNuvem.modo = "S3"
        configuracao = ConfiguracaoNuvem(
            provedor="S3",
            recipiente="balde",
            regiao="sa-east-1",
            endpoint=servidor_falso,
            prefixo="bussolapdv/",
        )
        cliente = criar_armazenamento(configuracao, ambiente=AMB_S3)

        original = tmp_path / "bussola.db"
        original.write_bytes(b"conteudo-do-backup")
        chave = enviar_backup(cliente, original)
        assert chave == "bussolapdv/bussola.db"

        # a requisição chegou assinada, no formato que o S3 exige
        pedido = _FalsoNuvem.pedidos[0]
        assert pedido["metodo"] == "PUT"
        assert pedido["headers"]["authorization"].startswith("AWS4-HMAC-SHA256 ")
        assert "x-amz-content-sha256" in pedido["headers"]
        assert pedido["headers"]["x-amz-server-side-encryption"] == "AES256"

        restaurado = cliente.baixar(chave, tmp_path / "restaurado.db")
        assert restaurado.read_bytes() == b"conteudo-do-backup"

        assert any(item.endswith("bussolapdv/bussola.db") for item in cliente.listar())
        cliente.remover(chave)
        assert cliente.listar() == []

    def test_listagem_sem_prefixo_quebrado(self, servidor_falso, tmp_path):
        _FalsoNuvem.modo = "S3"
        cliente = criar_armazenamento(
            ConfiguracaoNuvem(
                provedor="S3", recipiente="balde", endpoint=servidor_falso, prefixo="b/"
            ),
            ambiente=AMB_S3,
        )
        arquivo = tmp_path / "a.json"
        arquivo.write_bytes(b"{}")
        cliente.enviar(arquivo)
        chaves = cliente.listar()
        assert any(item.endswith("b/a.json") for item in chaves)

    def test_erro_do_provedor_vira_erro_de_nuvem(self, servidor_falso):
        cliente = criar_armazenamento(
            ConfiguracaoNuvem(provedor="S3", recipiente="balde", endpoint=servidor_falso),
            ambiente=AMB_S3,
        )
        with pytest.raises(ErroNuvem, match="404"):
            cliente.baixar("nao-existe.db", Path("saida/x.db"))

    def test_sem_credencial_o_cliente_nao_nasce(self, servidor_falso):
        with pytest.raises(NuvemNaoConfigurada, match="BUSSOLA_AWS_ACCESS_KEY_ID"):
            criar_armazenamento(
                ConfiguracaoNuvem(provedor="S3", recipiente="balde", endpoint=servidor_falso),
                ambiente={},
            )

    def test_variavel_customizada_e_respeitada(self, servidor_falso):
        configuracao = ConfiguracaoNuvem(
            provedor="S3",
            recipiente="balde",
            endpoint=servidor_falso,
            variavel_acesso="MINHA_KEY",
            variavel_chave="MEU_SEGREDO",
        )
        cliente = criar_armazenamento(
            configuracao, ambiente={"MINHA_KEY": "a", "MEU_SEGREDO": "s"}
        )
        assert cliente.chave_acesso == "a"


class TestAzure:
    def test_ida_e_volta_pelo_servidor_falso(self, servidor_falso, tmp_path):
        _FalsoNuvem.modo = "AZURE"
        configuracao = ConfiguracaoNuvem(
            provedor="AZURE_BLOB",
            recipiente="backups",
            conta="loja",
            endpoint=servidor_falso,
            prefixo="bussolapdv/",
        )
        cliente = criar_armazenamento(
            configuracao, ambiente={"BUSSOLA_AZURE_CHAVE": "Y2hhdmUtZGUtdGVzdGU="}
        )

        original = tmp_path / "bussola.db"
        original.write_bytes(b"backup-azure")
        chave = cliente.enviar(original)
        assert chave == "bussolapdv/bussola.db"

        pedido = _FalsoNuvem.pedidos[0]
        assert pedido["metodo"] == "PUT"
        assert pedido["headers"]["authorization"].startswith("SharedKey loja:")
        assert pedido["headers"]["x-ms-blob-type"] == "BlockBlob"
        assert pedido["headers"]["x-ms-version"]

        assert any(item.endswith("bussolapdv/bussola.db") for item in cliente.listar())
        assert cliente.baixar(chave, tmp_path / "volta.db").read_bytes() == b"backup-azure"
        cliente.remover(chave)

    def test_sem_chave_o_cliente_nao_nasce(self, servidor_falso):
        with pytest.raises(NuvemNaoConfigurada, match="BUSSOLA_AZURE_CHAVE"):
            criar_armazenamento(
                ConfiguracaoNuvem(
                    provedor="AZURE_BLOB", recipiente="c", conta="loja", endpoint=servidor_falso
                ),
                ambiente={},
            )

    def test_chave_fora_de_base64_da_erro_explicado(self, servidor_falso, tmp_path):
        configuracao = ConfiguracaoNuvem(
            provedor="AZURE_BLOB", recipiente="c", conta="loja", endpoint=servidor_falso
        )
        cliente = criar_armazenamento(
            configuracao, ambiente={"BUSSOLA_AZURE_CHAVE": "não-é-base64!!"}
        )
        arquivo = tmp_path / "a.bin"
        arquivo.write_bytes(b"x")
        with pytest.raises(ErroNuvem, match="base64"):
            cliente.enviar(arquivo)


class TestProvedorDesconhecido:
    def test_erro_cita_os_aceitos(self):
        from bussola_pdv.infra.nuvem import PROVEDORES

        with pytest.raises(ErroNuvem, match="S3"):
            ConfiguracaoNuvem(provedor="GCP", recipiente="b")
        assert PROVEDORES == ("S3", "AZURE_BLOB")


def test_backup_inexistente_nao_vai_para_a_nuvem(tmp_path):
    from bussola_pdv.infra.nuvem import ArmazenamentoMemoria

    with pytest.raises(ErroNuvem, match="inexistente"):
        enviar_backup(ArmazenamentoMemoria(), tmp_path / "nao-existe.db")


def test_configuracao_serializa_sem_segredo():
    configuracao = ConfiguracaoNuvem(
        provedor="S3", recipiente="balde", regiao="sa-east-1", prefixo="b/"
    )
    from dataclasses import asdict

    texto = json.dumps(asdict(configuracao))
    assert "segredo" not in texto.lower()
