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

from datetime import datetime
from pathlib import Path
from typing import cast

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.erros import ErroValidacao
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
    def relatorio_crediario(self, *, incluir_pagos: bool = False) -> Relatorio:
        titulos = ServicoCrediario(self.ctx).listar(incluir_pagos=incluir_pagos)
        # "Em aberto" é todo título com saldo — PARCIAL também deve saldo, e ignorar
        # isso subestimava o saldo da carteira no relatório.
        abertos = [titulo for titulo in titulos if int(titulo["saldo_centavos"]) > 0]
        vencidos = [titulo for titulo in abertos if int(titulo["atraso_dias"]) > 0]
        return Relatorio(
            titulo="Crediário",
            subtitulo="Títulos em aberto e recebidos — posição corrente",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(
                ("Títulos", str(len(titulos))),
                ("Inclui recebidos", "sim" if incluir_pagos else "não"),
            ),
            indicadores=(
                ("Em aberto", str(len(abertos))),
                ("Saldo aberto", _moeda(sum(int(t["saldo_centavos"]) for t in abertos))),
                ("Em atraso", str(len(vencidos))),
                (
                    "Saldo vencido",
                    _moeda(sum(int(t["saldo_centavos"]) for t in vencidos)),
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

    # -- clientes -----------------------------------------------------------
    def relatorio_clientes(self, busca: str = "") -> Relatorio:
        """Carteira de clientes com o que cada um deve no crediário.

        O documento mascarado é o mesmo da tela (`documento_mascarado`): exportar
        não é motivo para espalhar CPF/CNPJ inteiro em planilha.
        """
        clientes = self.ctx.clientes.listar(busca=busca, limite=5000)
        titulos = ServicoCrediario(self.ctx).listar()
        aberto: dict[str, int] = {}
        vencido: dict[str, int] = {}
        for titulo in titulos:
            if int(titulo["saldo_centavos"]) <= 0:
                continue
            cliente_id = titulo["cliente_id"]
            aberto[cliente_id] = aberto.get(cliente_id, 0) + int(titulo["saldo_centavos"])
            if int(titulo["atraso_dias"]) > 0:
                vencido[cliente_id] = vencido.get(cliente_id, 0) + int(titulo["saldo_centavos"])

        linhas = []
        for cliente in clientes:
            em_aberto = aberto.get(cliente.id, 0)
            linhas.append(
                (
                    cliente.nome,
                    cliente.documento_mascarado() if cliente.documento else "—",
                    cliente.limite_credito,
                    em_aberto,
                    max(0, cliente.limite_credito - em_aberto),
                    vencido.get(cliente.id, 0),
                    "ativo" if cliente.ativo else "inativo",
                )
            )
        return Relatorio(
            titulo="Clientes",
            subtitulo="Carteira com limite, saldo em aberto e valor vencido no crediário",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(
                ("Busca", busca or "(todas)"),
                ("Clientes", str(len(clientes))),
            ),
            indicadores=(
                ("Ativos", str(sum(1 for cliente in clientes if cliente.ativo))),
                ("Limite total", _moeda(sum(cliente.limite_credito for cliente in clientes))),
                ("Em aberto", _moeda(sum(aberto.values()))),
                ("Vencido", _moeda(sum(vencido.values()))),
            ),
            tabelas=(
                criar_tabela(
                    "Clientes",
                    [
                        ("Cliente", TipoColuna.TEXTO, 34),
                        ("Documento", TipoColuna.TEXTO, 20),
                        ("Limite", TipoColuna.MOEDA, 14),
                        ("Em aberto", TipoColuna.MOEDA, 14),
                        ("Disponível", TipoColuna.MOEDA, 14),
                        ("Vencido", TipoColuna.MOEDA, 14),
                        ("Situação", TipoColuna.TEXTO, 10),
                    ],
                    linhas,
                    nota=(
                        "Documento mascarado por padrão (LGPD): só os últimos 4 caracteres. "
                        "Em aberto e vencido vêm do crediário na data de negócio corrente."
                    ),
                ),
            ),
            avisos=(AVISO_FISCAL, "Saldo em aberto é posição corrente, não projeção."),
            escopo="Posição corrente da carteira; não reage a filtro de data.",
        )

    # -- estoque ------------------------------------------------------------
    def relatorio_estoque(self, busca: str = "") -> Relatorio:
        """Saldo, mínimo e ponto de pedido por produto — o que repor e quanto custa."""
        from ..dominio.produto import StatusEstoque, classificar_estoque

        produtos = self.ctx.produtos.listar(busca=busca, apenas_ativos=False, limite=5000)
        saldos = self.ctx.produtos.saldos()
        linhas = []
        por_status: dict[str, list[int]] = {status.value: [0, 0] for status in StatusEstoque}
        for produto in produtos:
            saldo = saldos.get(produto.id, 0)
            situacao = classificar_estoque(
                saldo,
                minimo_milesimos=produto.estoque_minimo_milesimos,
                ponto_pedido_milesimos=produto.ponto_pedido_milesimos,
            )
            custo = int(produto.custo) * saldo // 1000 if produto.ativo else 0
            if produto.ativo:
                por_status[situacao.value][0] += 1
                por_status[situacao.value][1] += custo
            linhas.append(
                (
                    produto.codigo,
                    produto.descricao,
                    produto.unidade.value,
                    _quantidade(saldo, produto.unidade.escala),
                    _quantidade(produto.estoque_minimo_milesimos, produto.unidade.escala),
                    _quantidade(produto.ponto_pedido_milesimos, produto.unidade.escala),
                    situacao.value if produto.ativo else "INATIVO",
                    custo,
                )
            )
        return Relatorio(
            titulo="Estoque",
            subtitulo="Saldo, mínimo, ponto de pedido e valor a custo por produto",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(("Busca", busca or "(todas)"), ("Produtos", str(len(produtos)))),
            indicadores=(
                ("Ruptura", str(por_status[StatusEstoque.RUPTURA.value][0])),
                ("Abaixo do mínimo", str(por_status[StatusEstoque.BAIXO.value][0])),
                (
                    "Valor a custo",
                    _moeda(sum(valores[1] for valores in por_status.values())),
                ),
            ),
            tabelas=(
                criar_tabela(
                    "Produtos",
                    [
                        ("Código", TipoColuna.TEXTO, 12),
                        ("Descrição", TipoColuna.TEXTO, 34),
                        ("Un.", TipoColuna.TEXTO, 6),
                        ("Saldo", TipoColuna.TEXTO, 12),
                        ("Mínimo", TipoColuna.TEXTO, 12),
                        ("Ponto de pedido", TipoColuna.TEXTO, 14),
                        ("Situação", TipoColuna.TEXTO, 12),
                        ("Valor a custo", TipoColuna.MOEDA, 15),
                    ],
                    linhas,
                    nota=(
                        "Saldo é posição corrente do livro de movimentos; não é inventário "
                        "contábil nem contagem física."
                    ),
                ),
                criar_tabela(
                    "Resumo por situação",
                    [
                        ("Situação", TipoColuna.TEXTO, 22),
                        ("Produtos", TipoColuna.INTEIRO, 12),
                        ("Valor a custo", TipoColuna.MOEDA, 16),
                    ],
                    [(status, valores[0], valores[1]) for status, valores in por_status.items()],
                    nota="Só produtos ativos entram no resumo por situação.",
                ),
            ),
            avisos=(AVISO_FISCAL,),
            escopo="Posição corrente; não reage a filtro de data.",
        )

    # -- turno de caixa -----------------------------------------------------
    def relatorio_turno(self, turno_id: str | None = None) -> Relatorio:
        """Fechamento do turno: dinheiro esperado, movimentos e contagem.

        Sem `turno_id`, usa os turnos **abertos** — é o que a tela de Caixa
        exporta quando o operador clica em Exportar no meio do expediente. Com
        `turno_id`, exporta exatamente aquele turno (inclusive já fechado).
        """
        from ..dominio.caixa import conferir_turno
        from ..dominio.dinheiro import Dinheiro

        if turno_id:
            registrados = [self.ctx.caixas.turno_por_id(turno_id)]
        else:
            registrados = list(self.ctx.caixas.turnos_abertos())
        if not registrados:
            raise ErroValidacao(
                "Nenhum turno aberto para exportar. Abra o caixa ou exporte pelo "
                "fechamento do dia."
            )

        nomes_de_caixa = {caixa["id"]: caixa["nome"] for caixa in self.ctx.caixas.listar_caixas()}
        tabelas: list[Tabela] = []
        esperado_total = 0
        diferenca_total = 0
        conferidos = 0

        for registrado in registrados:
            turno = self.ctx.caixas.carregar_turno(registrado.id)
            contagens = self.ctx.caixas.contagens(registrado.id)
            conferencia = conferir_turno(turno, contagens) if contagens else None
            # `resumo` devolve todos os totais do turno; sem contagem, contado = 0.
            valores = conferencia or turno.resumo(Dinheiro.zero())
            esperado = _centavos(valores["esperado_centavos"])
            esperado_total += esperado
            if conferencia:
                conferidos += 1
                diferenca_total += _centavos(conferencia["diferenca_centavos"])

            etiqueta = nomes_de_caixa.get(registrado.caixa_id, registrado.caixa_id[:8])
            sufixo = f"{etiqueta} · {registrado.id[:8]}"

            itens: list[tuple[str, str]] = [
                ("Caixa", etiqueta),
                ("Operador", self._nome_de_usuario(registrado.operador_id)),
                ("Status", registrado.status.value),
                ("Aberto em", _carimbo(registrado.aberto_em)),
                ("Fechado em", _carimbo(registrado.fechado_em) or "—"),
                ("Fundo de troco", _moeda(valores["fundo_centavos"])),
                ("Vendas em dinheiro", _moeda(valores["vendas_dinheiro_centavos"])),
                ("Recebimentos de títulos", _moeda(valores["recebimentos_centavos"])),
                ("Suprimentos", _moeda(valores["suprimentos_centavos"])),
                ("Sangrias", _moeda(valores["sangrias_centavos"])),
                ("Estornos", _moeda(valores["estornos_centavos"])),
                ("Esperado na gaveta", _moeda(esperado)),
            ]
            if conferencia:
                itens += [
                    ("Contado", _moeda(conferencia["contado_centavos"])),
                    ("Diferença", _moeda(conferencia["diferenca_centavos"])),
                    ("Classificação", str(conferencia["classificacao"])),
                ]
            else:
                itens.append(("Conferência", "não conferido (sem contagem registrada)"))
            tabelas.append(
                criar_tabela(
                    f"Caixa e dinheiro — {sufixo}",
                    [("Item", TipoColuna.TEXTO, 30), ("Valor", TipoColuna.TEXTO, 34)],
                    itens,
                    nota=(
                        "Esperado = fundo + vendas em dinheiro + recebimentos + suprimentos "
                        "− sangrias − estornos."
                    ),
                )
            )

            tabelas.append(
                criar_tabela(
                    f"Movimentos do turno — {sufixo}",
                    [
                        ("Tipo", TipoColuna.TEXTO, 22),
                        ("Valor", TipoColuna.MOEDA, 14),
                        ("Motivo", TipoColuna.TEXTO, 34),
                        ("Autorizador", TipoColuna.TEXTO, 22),
                    ],
                    [
                        (
                            movimento.tipo.value,
                            movimento.valor.centavos,
                            movimento.motivo or "—",
                            self._nome_de_usuario(movimento.autorizador_id),
                        )
                        for movimento in turno.movimentos
                    ],
                    nota="Sangria e suprimento exigem motivo; valores são sempre positivos.",
                )
            )

            if conferencia:
                tabelas.append(
                    criar_tabela(
                        f"Contagem por denominação — {sufixo}",
                        [
                            ("Denominação", TipoColuna.TEXTO, 16),
                            ("Quantidade", TipoColuna.INTEIRO, 12),
                            ("Subtotal", TipoColuna.MOEDA, 16),
                        ],
                        [
                            (linha["rotulo"], linha["quantidade"], linha["subtotal_centavos"])
                            for linha in cast(
                                list[dict[str, object]], conferencia["contagens"]
                            )
                        ],
                        nota="Contagem registrada pelo conferente no fechamento do turno.",
                    )
                )

        return Relatorio(
            titulo="Fechamento do turno",
            subtitulo="Conferência da gaveta: dinheiro esperado, movimentos e contagem",
            loja=self._loja(),
            identificacao=self._identificacao(),
            filtros=(
                (
                    "Turno",
                    registrados[0].id[:8]
                    if len(registrados) == 1
                    else f"{len(registrados)} turnos abertos",
                ),
                ("Data de negócio", registrados[0].data_negocio),
            ),
            indicadores=(
                ("Turnos", str(len(registrados))),
                ("Esperado na gaveta", _moeda(esperado_total)),
                ("Diferença", _moeda(diferenca_total)),
                ("Conferidos", f"{conferidos} de {len(registrados)}"),
            ),
            tabelas=tuple(tabelas),
            avisos=(AVISO_FISCAL, "Conferência aritmética de gaveta; não é fechamento contábil."),
            escopo="Escopo do turno: fundo, vendas em dinheiro, movimentos de caixa e contagem.",
        )

    def _nome_de_usuario(self, usuario_id: str | None) -> str:
        if not usuario_id:
            return "—"
        try:
            return self.ctx.usuarios.por_id(usuario_id).nome
        except Exception:  # pragma: no cover - usuário removido/sem permissão de leitura
            return usuario_id[:8]

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

    def exportar_crediario(
        self, usuario: Usuario, destino: Path, *, incluir_pagos: bool = False
    ) -> Path:
        return self.exportar(
            usuario, self.relatorio_crediario(incluir_pagos=incluir_pagos), destino
        )

    def exportar_clientes(self, usuario: Usuario, destino: Path, busca: str = "") -> Path:
        return self.exportar(usuario, self.relatorio_clientes(busca), destino)

    def exportar_estoque(self, usuario: Usuario, destino: Path, busca: str = "") -> Path:
        return self.exportar(usuario, self.relatorio_estoque(busca), destino)

    def exportar_turno(
        self, usuario: Usuario, destino: Path, turno_id: str | None = None
    ) -> Path:
        return self.exportar(usuario, self.relatorio_turno(turno_id), destino)

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


def _centavos(valor: object) -> int:
    """Centavos de um `dict[str, object]` (resumo do turno e conferência)."""
    return valor if isinstance(valor, int) else int(str(valor))


def _carimbo(quando: datetime | None) -> str:
    """Data/hora legível no fuso do computador da loja."""
    if quando is None:
        return ""
    return quando.astimezone().strftime("%d/%m/%Y %H:%M")


def _moeda(centavos: object) -> str:
    from ..infra.exportacao.formato import moeda

    return moeda(centavos)


def _quantidade(milesimos: int, escala: int) -> str:
    """Saldo em milésimos → texto com a precisão da unidade (3 casas para KG)."""
    if escala == 0:
        return str(milesimos // 1000)
    return f"{milesimos / 1000:.3f}".replace(".", ",")


__all__ = ["AVISO_FISCAL", "Coluna", "ServicoExportacao"]
