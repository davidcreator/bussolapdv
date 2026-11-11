"""Marca da loja e tema como dado persistido, com auditoria.

Quem mexe em identidade não mexe em permissão, e vice-versa: `MARCA_GERENCIAR`
cobre dados da loja e `TEMA_GERENCIAR` cobre cores/fonte. Um Admin pode receber
só o primeiro, por exemplo, para trocar o telefone do rodapé sem redesenhar a
interface.
"""

from __future__ import annotations

import base64

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.erros import ErroValidacao
from ..dominio.marca import PALETAS_PADRAO, Marca, Paleta
from ..dominio.usuario import Acao, Usuario
from .contexto import Contexto


class ServicoMarca:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    def obter(self) -> Marca:
        """Leitura pública: qualquer usuário precisa do nome da loja na tela."""
        return Marca.de_parametros(self.ctx.parametros.por_prefixo("marca."))

    def presets(self) -> dict[str, Paleta]:
        return dict(PALETAS_PADRAO)

    def salvar(self, ator: Usuario, marca: Marca) -> Marca:
        atual = self.obter()
        dados_mudaram = (
            marca.nome_fantasia,
            marca.razao_social,
            marca.cnpj,
            marca.telefone,
            marca.endereco,
            marca.rodape_comprovante,
            marca.logo_data_uri,
        ) != (
            atual.nome_fantasia,
            atual.razao_social,
            atual.cnpj,
            atual.telefone,
            atual.endereco,
            atual.rodape_comprovante,
            atual.logo_data_uri,
        )
        tema_mudou = (marca.paleta, marca.fonte, marca.preset) != (
            atual.paleta,
            atual.fonte,
            atual.preset,
        )
        if not dados_mudaram and not tema_mudou:
            return atual
        if dados_mudaram:
            ator.exigir(Acao.MARCA_GERENCIAR)
        if tema_mudou:
            ator.exigir(Acao.TEMA_GERENCIAR)

        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.parametros.definir_varios(marca.a_parametros(), agora_iso=agora.isoformat())
            # `empresa.nome` alimenta relatórios e cabeçalhos legados: mantém sincronizado.
            self.ctx.parametros.definir(
                "empresa.nome", marca.nome_fantasia, agora_iso=agora.isoformat()
            )
            self.ctx.parametros.definir(
                "empresa.cnpj", marca.cnpj, agora_iso=agora.isoformat()
            )
            if dados_mudaram:
                self.ctx.auditoria.registrar(
                    EventoAuditoria(
                        acao=AcaoAuditoria.MARCA_ALTERADA,
                        criado_em_utc=agora,
                        data_negocio=self.ctx.relogio.data_negocio(),
                        ator_id=ator.id,
                        entidade="marca",
                        entidade_id=marca.nome_fantasia,
                        antes=self._resumo(atual),
                        depois=self._resumo(marca),
                        motivo="Alteração da identidade da loja",
                    )
                )
            if tema_mudou:
                self.ctx.auditoria.registrar(
                    EventoAuditoria(
                        acao=AcaoAuditoria.TEMA_ALTERADO,
                        criado_em_utc=agora,
                        data_negocio=self.ctx.relogio.data_negocio(),
                        ator_id=ator.id,
                        entidade="tema",
                        entidade_id=marca.preset,
                        antes={"preset": atual.preset, "paleta": atual.paleta.a_dicionario()},
                        depois={"preset": marca.preset, "paleta": marca.paleta.a_dicionario()},
                        motivo="Alteração de cores/tema",
                    )
                )
        return self.obter()

    def aplicar_preset(self, ator: Usuario, preset: str) -> Marca:
        return self.salvar(ator, self.obter().com_preset(preset))

    def restaurar_padrao(self, ator: Usuario) -> Marca:
        return self.salvar(ator, Marca.padrao())

    def logo_de_arquivo(self, caminho: str) -> str:
        """Lê um PNG do disco e devolve o data URI validado (máx. 200 KB)."""
        from pathlib import Path

        arquivo = Path(caminho)
        if not arquivo.is_file():
            raise ErroValidacao("Arquivo de logo não encontrado.")
        conteudo = arquivo.read_bytes()
        if not conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ErroValidacao("O logo precisa ser um arquivo PNG.")
        dados = base64.b64encode(conteudo).decode("ascii")
        logo = f"data:image/png;base64,{dados}"
        Marca._validar_logo(logo)  # valida tamanho pela mesma regra do domínio
        return logo

    def _resumo(self, marca: Marca) -> dict[str, object]:
        return {
            "nome_fantasia": marca.nome_fantasia,
            "razao_social": marca.razao_social,
            "cnpj": marca.cnpj,
            "telefone": marca.telefone,
            "endereco": marca.endereco,
            "logo": bool(marca.logo_data_uri),
        }
