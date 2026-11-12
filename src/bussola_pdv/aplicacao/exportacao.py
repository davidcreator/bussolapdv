"""Exportação de relatórios: monta o `Relatorio` e grava em Excel ou PDF.

Três decisões que valem registro:

1. **A permissão é `EXPORTAR_DADOS`**, a mesma que já existia na matriz de
   perfis. Exportar é tirar dado da loja: gerente, contabilidade, admin e master
   têm; atendente não tem.
2. **Toda exportação deixa rastro.** O evento `DADOS_EXPORTADOS` grava formato,
   quantidade de linhas e nome do arquivo na trilha append-only. Sem isso,
   "quem levou o fechamento do dia 12?" seria pergunta sem resposta.
3. **Nada é montado na UI.** A tela pede o relatório ao serviço e entrega ao
   exportador; o arquivo e a tela mostram os mesmos números porque a fonte é a
   mesma consulta.

O arquivo gerado é **documento interno**: não é nota fiscal, não substitui
relatório contábil assinado e não confirma liquidação de PIX/cartão.
"""

from __future__ import annotations

from pathlib import Path

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.marca import Marca
from ..dominio.relatorio import (
    DOCUMENTO_INTERNO,
    Coluna,
    Relatorio,
    Tabela,
    TipoColuna,
    criar_tabela,
)
from ..dominio.usuario import Acao, Usuario
from ..infra import exportacao as formatos
from .contexto import Contexto
from .crediario import ServicoCrediario
from .marca import ServicoMarca
from .relatorios import ServicoRelatorios

AVISO_FISCAL = "Documento interno de conferência: não é documento fiscal."


class ServicoExportacao:
    """Do banco ao arquivo: relatório, arquivo e evento de auditoria."""

    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto
        self.relatorios = ServicoRelatorios(contexto)

    # -- identidade da loja --------------------------------------------------
    def _marca(self) -> Marca | None:
        try:
            return ServicoMarca(self.ctx).obter()
        except Exception:  # pragma: no cover - base recém-criada não tem marca
            return None

    def _loja(self) -> str:
        marca = self._marca()
        return (marca.nome_fantasia if marca else "") or "Bússola Sistema PDV"

    def _identificacao(self) -> tuple[tuple[str, str], ...]:
        marca = self._marca()
        if marca is None:  # pragma: no cover - defensivo
            return ()
        linhas = [("Loja", marca.nome_fantasia)]
        if marca.cnpj:
            linhas.append(("CNPJ", marca.cnpj))
        if marca.telefone:
            linhas.append(("Telefone", marca.telefone))
        if marca.endereco:
            linhas.append(("Endereço", marca.endereco))
        return tuple(linhas)

    # -- fechamento do caixa -------------------------------------------------
    def relatorio_fechamento(self, data_negocio: str) -> Relatorio:
        """Fechamento do dia no formato exportável (Excel e PDF)."""
        dados = self.relatorios.fechamento_dia(data_negocio)
        resumo = dados["resumo"]
        conciliacao = dados["conciliacao"]
        estoque = dados["estoque"]
        crediario = dados["crediario_do_dia"]

        indicadores = (
            ("Cupons", str(resumo["cupons"])),
            ("Faturamento", _moeda(resumo["faturamento_centavos"])),
            ("Ticket médio", _moeda(resumo["ticket_medio_centavos"])),
            ("Descontos", _moeda(resumo["desconto_centavos"])),
            ("Conciliação", "CONCILIADO" if conciliacao["conciliado"] else "DIVERGENTE"),
        )

        tabelas: list[Tabela] = [
            criar_tabela(
                "Resumo do dia",
                [("Indicador", TipoColuna.TEXTO, 30), ("Valor", TipoColuna.TEXTO, 22)],
                [
                    ("Cupons concluídos", resumo["cupons"]),
                    ("Subtotal", _moeda(resumo["subtotal_centavos"])),
                    ("Descontos", _moeda(resumo["desconto_centavos"])),
                    ("Faturamento líquido", _moeda(resumo["faturamento_centavos"])),
                    ("Custo dos itens", _moeda(resumo["custo_centavos"])),
                    ("Ticket médio", _moeda(resumo["ticket_medio_centavos"])),
                ],
                nota="Faturamento é soma dos cupons CONCLUIDA; troco não é receita.",
            ),
            criar_tabela(
                "Por forma de pagamento",
                [
                    ("Forma", TipoColuna.TEXTO, 26),
                    ("Aplicado", TipoColuna.MOEDA, 16),
                    ("Entregue", TipoColuna.MOEDA, 16),
                    ("Troco", TipoColuna.MOEDA, 14),
                    ("Pendente", TipoColuna.MOEDA, 16),
                    ("Lançamentos", TipoColuna.INTEIRO, 12),
                ],
                [
                    (
                        forma["rotulo"],
                        forma["aplicado_centavos"],
                        forma["entregue_centavos"],
                        forma["troco_centavos"],
                        forma["pendente_centavos"],
                        forma["linhas"],
                    )
                    for forma in dados["por_forma"]
                ],
                nota="Valor aplicado é o que compõe faturamento; entregue inclui troco.",
            ),
            criar_tabela(
                "Por operador",
                [
                    ("Operador", TipoColuna.TEXTO, 30),
                    ("Cupons", TipoColuna.INTEIRO, 12),
                    ("Total", TipoColuna.MOEDA, 16),
                ],
                [
                    (linha["operador"], linha["cupons"], linha["total_centavos"])
                    for linha in dados["por_operador"]
                ],
            ),
            criar_tabela(
                "Conciliação",
                [("Item", TipoColuna.TEXTO, 34), ("Valor", TipoColuna.TEXTO, 22)],
                [
                    ("Pagamentos aplicados", _moeda(conciliacao["pagamentos_aplicados_centavos"])),
                    ("Faturamento", _moeda(conciliacao["faturamento_centavos"])),
                    ("Diferença", _moeda(conciliacao["diferenca_centavos"])),
                    ("Situação", "CONCILIADO" if conciliacao["conciliado"] else "DIVERGENTE"),
                ],
                nota=conciliacao["aviso"],
            ),
            criar_tabela(
                "Turnos de caixa",
                [
                    ("Turno", TipoColuna.TEXTO, 14),
                    ("Status", TipoColuna.TEXTO, 12),
                    ("Esperado", TipoColuna.MOEDA, 15),
                    ("Contado", TipoColuna.MOEDA, 15),
                    ("Diferença", TipoColuna.MOEDA, 15),
                    ("Conferência", TipoColuna.TEXTO, 20),
                ],
                [
                    (
                        turno["turno_id"][:8],
                        turno["status"],
                        turno.get("esperado_centavos", 0),
                        turno.get("contado_centavos", 0),
                        turno.get("diferenca_centavos", 0),
                        (
                            turno.get("classificacao", "")
                            if turno.get("conferido")
                            else "não conferido"
                        ),
                    )
                    for turno in dados["turnos"]
                ],
                nota="Diferença só existe depois da contagem por denominação.",
            ),
        ]

        if dados["pagamentos_pendentes"]:
            tabelas.append(
                criar_tabela(
                    "Pagamentos pendentes de confirmação",
                    [
                        ("Cupom", TipoColuna.TEXTO, 16),
                        ("Forma", TipoColuna.TEXTO, 18),
                        ("Valor aplicado", TipoColuna.MOEDA, 18),
                    ],
                    [
                        (
                            f"1-{pendente['numero']:06d}",
                            pendente["forma"],
                            pendente["valor_aplicado_centavos"],
                        )
                        for pendente in dados["pagamentos_pendentes"]
                    ],
                    nota="PIX e cartão nascem pendentes e exigem confirmação registrada.",
                )
            )

        tabelas.append(
            criar_tabela(
                "Estoque por situação",
                [("Situação", TipoColuna.TEXTO, 22), ("Produtos", TipoColuna.INTEIRO, 14)],
                list(estoque["por_status"].items()),
                nota=(
                    f"Valor a custo: {_moeda(estoque['valor_custo_centavos'])}. "
                    f"{estoque['escopo']}"
                ),
            )
        )
        tabelas.append(
            criar_tabela(
                "Crediário",
                [("Indicador", TipoColuna.TEXTO, 30), ("Valor", TipoColuna.TEXTO, 22)],
                [
                    ("Títulos abertos", crediario["titulos_abertos"]),
                    ("Saldo aberto", _moeda(crediario["saldo_aberto_centavos"])),
                    ("Vencendo hoje", _moeda(crediario["vencendo_hoje_centavos"])),
                ],
                nota=crediario["escopo"],
            )
        )

        avisos = [AVISO_FISCAL, conciliacao["aviso"]]
        for chave, lista in dados["divergencias"].items():
            if lista:
                avisos.append(f"{chave}: {len(lista)} registro(s) para investigar.")

        return Relatorio(
            titulo="Fechamento do caixa",
            subtitulo="Conferência aritmética do dia — não representa confirmação bancária",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(
                ("Data de negócio", data_negocio),
                ("Escopo", "data comercial e status CONCLUIDA"),
            ),
            indicadores=indicadores,
            tabelas=tuple(tabelas),
            avisos=tuple(avisos),
            escopo=dados["escopo"],
        )

    # -- vendas do período ---------------------------------------------------
    def relatorio_vendas(self, data_inicial: str, data_final: str) -> Relatorio:
        vendas = self.ctx.vendas.listar(
            data_inicial=data_inicial, data_final=data_final, limite=5000
        )
        concluidas = [venda for venda in vendas if venda["status"] == "CONCLUIDA"]
        faturamento = sum(int(venda["total_centavos"]) for venda in concluidas)
        ticket = faturamento // len(concluidas) if concluidas else 0
        return Relatorio(
            titulo="Vendas do período",
            subtitulo="Cupons por data de negócio, incluindo cancelados quando houver",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(("Período", f"{data_inicial} a {data_final}"),),
            indicadores=(
                ("Cupons concluídos", str(len(concluidas))),
                ("Cancelados", str(len(vendas) - len(concluidas))),
                ("Faturamento", _moeda(faturamento)),
                ("Ticket médio", _moeda(ticket)),
            ),
            tabelas=(
                criar_tabela(
                    "Cupons",
                    [
                        ("Cupom", TipoColuna.TEXTO, 14),
                        ("Data", TipoColuna.DATA, 12),
                        ("Operador", TipoColuna.TEXTO, 24),
                        ("Cliente", TipoColuna.TEXTO, 24),
                        ("Itens", TipoColuna.INTEIRO, 8),
                        ("Total", TipoColuna.MOEDA, 14),
                        ("Aplicado", TipoColuna.MOEDA, 14),
                        ("Status", TipoColuna.TEXTO, 12),
                    ],
                    [
                        (
                            f"{venda['serie']}-{venda['numero']:06d}",
                            venda["data_negocio"],
                            venda["operador"],
                            venda["cliente"] or "—",
                            venda["itens"],
                            venda["total_centavos"],
                            venda["aplicado_centavos"],
                            venda["status"],
                        )
                        for venda in vendas
                    ],
                    nota="Cancelamento exige autorização e motivo registrado na auditoria.",
                ),
            ),
            avisos=(AVISO_FISCAL,),
            escopo="Filtro: data de negócio entre o início e o fim informados.",
        )

    # -- catálogo e estoque --------------------------------------------------
    def relatorio_catalogo(self, busca: str = "") -> Relatorio:
        produtos = self.ctx.produtos.listar(busca=busca, apenas_ativos=False, limite=5000)
        saldos = self.ctx.produtos.saldos()
        from ..dominio.produto import classificar_estoque

        linhas = []
        valor_custo = 0
        for produto in produtos:
            saldo = saldos.get(produto.id, 0)
            situacao = classificar_estoque(
                saldo,
                minimo_milesimos=produto.estoque_minimo_milesimos,
                ponto_pedido_milesimos=produto.ponto_pedido_milesimos,
            )
            if produto.ativo:
                valor_custo += int(produto.custo) * saldo // 1000
            linhas.append(
                (
                    produto.codigo,
                    produto.descricao,
                    produto.categoria,
                    produto.unidade.value,
                    produto.custo,
                    produto.preco,
                    _quantidade(saldo, produto.unidade.escala),
                    situacao.value if produto.ativo else "INATIVO",
                )
            )
        return Relatorio(
            titulo="Catálogo e estoque",
            subtitulo="Posição corrente de saldo e preço — não é inventário contábil",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(
                ("Busca", busca or "(todas)"),
                ("Produtos", str(len(produtos))),
            ),
            indicadores=(
                ("Produtos ativos", str(sum(1 for produto in produtos if produto.ativo))),
                ("Valor a custo", _moeda(valor_custo)),
            ),
            tabelas=(
                criar_tabela(
                    "Produtos",
                    [
                        ("Código", TipoColuna.TEXTO, 12),
                        ("Descrição", TipoColuna.TEXTO, 34),
                        ("Categoria", TipoColuna.TEXTO, 18),
                        ("Un.", TipoColuna.TEXTO, 6),
                        ("Custo", TipoColuna.MOEDA, 12),
                        ("Preço", TipoColuna.MOEDA, 12),
                        ("Saldo", TipoColuna.TEXTO, 12),
                        ("Situação", TipoColuna.TEXTO, 12),
                    ],
                    linhas,
                    nota=(
                        "Saldo em milésimos da unidade convertido para leitura; "
                        "situação vem da regra de estoque do domínio."
                    ),
                ),
            ),
            avisos=(AVISO_FISCAL,),
            escopo="Posição corrente; não reage a filtro de data.",
        )

    # -- auditoria -----------------------------------------------------------
    def relatorio_auditoria(self, limite: int = 500) -> Relatorio:
        eventos = self.ctx.auditoria.listar(limite=limite)
        verificacao = self.ctx.auditoria.verificar()
        return Relatorio(
            titulo="Trilha de auditoria",
            subtitulo="Eventos mais recentes, ordem decrescente",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(("Eventos", str(len(eventos))),),
            indicadores=(("Integridade da cadeia", "íntegra" if verificacao.integro else "FALHA"),),
            tabelas=(
                criar_tabela(
                    "Eventos",
                    [
                        ("Seq.", TipoColuna.INTEIRO, 8),
                        ("Quando (UTC)", TipoColuna.TEXTO, 20),
                        ("Ação", TipoColuna.TEXTO, 24),
                        ("Ator", TipoColuna.TEXTO, 34),
                        ("Entidade", TipoColuna.TEXTO, 22),
                        ("Motivo", TipoColuna.TEXTO, 40),
                    ],
                    [
                        (
                            evento.sequencia,
                            evento.criado_em_utc.strftime("%d/%m/%Y %H:%M:%S"),
                            evento.acao.value,
                            evento.ator_id or "—",
                            f"{evento.entidade}:{evento.entidade_id[:8]}"
                            if evento.entidade_id
                            else "—",
                            evento.motivo,
                        )
                        for evento in eventos
                    ],
                    nota=verificacao.mensagem,
                ),
            ),
            avisos=(AVISO_FISCAL,),
            escopo="Trilha append-only: UPDATE e DELETE são bloqueados por trigger.",
        )

    # -- crediário -----------------------------------------------------------
    def relatorio_crediario(self) -> Relatorio:
        titulos = ServicoCrediario(self.ctx).listar()
        abertos = [titulo for titulo in titulos if titulo["status"] == "ABERTO"]
        return Relatorio(
            titulo="Crediário",
            subtitulo="Títulos em aberto e recebidos — posição corrente",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(("Títulos", str(len(titulos))),),
            indicadores=(
                ("Em aberto", str(len(abertos))),
                ("Saldo aberto", _moeda(sum(int(t["saldo_centavos"]) for t in abertos))),
                (
                    "Em atraso",
                    str(sum(1 for t in abertos if int(t["atraso_dias"]) > 0)),
                ),
            ),
            tabelas=(
                criar_tabela(
                    "Títulos",
                    [
                        ("Cliente", TipoColuna.TEXTO, 30),
                        ("Parcela", TipoColuna.TEXTO, 10),
                        ("Vencimento", TipoColuna.DATA, 12),
                        ("Principal", TipoColuna.MOEDA, 14),
                        ("Recebido", TipoColuna.MOEDA, 14),
                        ("Saldo", TipoColuna.MOEDA, 14),
                        ("Atraso (dias)", TipoColuna.INTEIRO, 12),
                        ("Status", TipoColuna.TEXTO, 12),
                    ],
                    [
                        (
                            titulo["cliente"],
                            f"{titulo['numero_parcela']}/{titulo['total_parcelas']}",
                            titulo["vencimento"],
                            titulo["principal_centavos"],
                            titulo["recebido_centavos"],
                            titulo["saldo_centavos"],
                            titulo["atraso_dias"],
                            titulo["status"],
                        )
                        for titulo in titulos
                    ],
                ),
            ),
            avisos=(AVISO_FISCAL,),
            escopo="Posição corrente do crediário; não é filtrada por data.",
        )

    # -- escrita com permissão e auditoria -----------------------------------
    def exportar(self, usuario: Usuario, relatorio: Relatorio, destino: Path) -> Path:
        """Grava o arquivo e registra o evento. Exige `EXPORTAR_DADOS`."""
        usuario.exigir(Acao.EXPORTAR_DADOS)
        destino = Path(destino)
        caminho = formatos.escrever(relatorio, destino)
        self._registrar(usuario, relatorio, caminho)
        return caminho

    def exportar_fechamento(self, usuario: Usuario, data_negocio: str, destino: Path) -> Path:
        return self.exportar(usuario, self.relatorio_fechamento(data_negocio), destino)

    def exportar_vendas(
        self, usuario: Usuario, data_inicial: str, data_final: str, destino: Path
    ) -> Path:
        return self.exportar(usuario, self.relatorio_vendas(data_inicial, data_final), destino)

    def exportar_catalogo(self, usuario: Usuario, destino: Path, busca: str = "") -> Path:
        return self.exportar(usuario, self.relatorio_catalogo(busca), destino)

    def exportar_auditoria(self, usuario: Usuario, destino: Path, limite: int = 500) -> Path:
        return self.exportar(usuario, self.relatorio_auditoria(limite), destino)

    def exportar_crediario(self, usuario: Usuario, destino: Path) -> Path:
        return self.exportar(usuario, self.relatorio_crediario(), destino)

    def _data_negocio(self, relatorio: Relatorio) -> str:
        """Data do evento: a do filtro, quando existe; senão, a data comercial de hoje."""
        for rotulo, valor in relatorio.filtros:
            if rotulo.lower().startswith("data"):
                return valor
        return self.ctx.data_negocio()

    def _registrar(self, usuario: Usuario, relatorio: Relatorio, caminho: Path) -> None:
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.DADOS_EXPORTADOS,
                    criado_em_utc=agora,
                    data_negocio=self._data_negocio(relatorio),
                    ator_id=usuario.id,
                    entidade="relatorio",
                    entidade_id=caminho.name,
                    depois={
                        "titulo": relatorio.titulo,
                        "formato": caminho.suffix.lower().lstrip("."),
                        "linhas": relatorio.linhas,
                        "filtros": dict(relatorio.filtros),
                        "documento": DOCUMENTO_INTERNO,
                    },
                    motivo=f"Exportação de relatório em {caminho.suffix.lower().lstrip('.')}",
                )
            )


def _moeda(centavos: object) -> str:
    from ..infra.exportacao.formato import moeda

    return moeda(centavos)


def _quantidade(milesimos: int, escala: int) -> str:
    """Saldo em milésimos → texto com a precisão da unidade (3 casas para KG)."""
    if escala == 0:
        return str(milesimos // 1000)
    return f"{milesimos / 1000:.3f}".replace(".", ",")


__all__ = ["AVISO_FISCAL", "Coluna", "ServicoExportacao"]
