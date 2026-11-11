"""Fechamento, conciliação e indicadores — sempre com escopo explícito."""

from __future__ import annotations

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.caixa import conferir_turno
from ..dominio.dinheiro import Dinheiro
from ..dominio.produto import StatusEstoque
from ..dominio.usuario import Acao, Usuario
from .contexto import Contexto
from .crediario import ServicoCrediario


class ServicoRelatorios:
    """Relatórios reconciliados por ID e status.

    Regra de ouro: valor **aplicado** é faturamento/pagamento; valor **entregue**
    é o que o cliente passou na mão; troco não é receita. Nenhum total aqui
    confirma liquidação bancária.
    """

    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- fechamento do dia --------------------------------------------------
    def fechamento_dia(self, data_negocio: str, *, operador: Usuario | None = None) -> dict:
        resumo = self.ctx.vendas.resumo_periodo(data_negocio, data_negocio)
        formas = self.ctx.vendas.por_forma(data_negocio, data_negocio)
        divergencias = self.ctx.vendas.divergencias(data_negocio, data_negocio)
        pendentes = self.ctx.vendas.pendentes_confirmacao(data_negocio, data_negocio)
        turnos = self.ctx.caixas.turnos_do_dia(data_negocio)

        conferencias_turno = []
        for turno in turnos:
            carregado = self.ctx.caixas.carregar_turno(turno.id)
            contagens = self.ctx.caixas.contagens(turno.id)
            if contagens:
                conferencias_turno.append(
                    {
                        "turno_id": turno.id,
                        "status": turno.status.value,
                        "conferido": True,
                        **conferir_turno(carregado, contagens),
                    }
                )
            elif turno.status.value == "ABERTO":
                # Turno aberto ainda não foi contado: não existe diferença a apurar.
                conferencias_turno.append(
                    {
                        "turno_id": turno.id,
                        "status": turno.status.value,
                        "conferido": False,
                        "esperado_centavos": carregado.esperado.centavos,
                    }
                )
            else:
                conferencias_turno.append(
                    {
                        "turno_id": turno.id,
                        "status": turno.status.value,
                        "conferido": False,
                        **carregado.resumo(turno.contado or Dinheiro.zero()),
                    }
                )

        aplicado = sum(int(forma["aplicado_centavos"]) for forma in formas)
        diferenca = aplicado - int(resumo["faturamento_centavos"])

        operadores = [
            dict(linha)
            for linha in self.ctx.conexao.execute(
                """SELECT v.operador_id, u.nome AS operador, COUNT(*) AS cupons,
                          COALESCE(SUM(v.total_centavos), 0) AS total_centavos
                     FROM vendas v JOIN usuarios u ON u.id = v.operador_id
                    WHERE v.data_negocio = ? AND v.status = 'CONCLUIDA'
                    GROUP BY v.operador_id ORDER BY total_centavos DESC""",
                (data_negocio,),
            )
        ]

        return {
            "data_negocio": data_negocio,
            "resumo": resumo,
            "por_forma": formas,
            "por_operador": operadores,
            "turnos": conferencias_turno,
            "conciliacao": {
                "pagamentos_aplicados_centavos": aplicado,
                "faturamento_centavos": int(resumo["faturamento_centavos"]),
                "diferenca_centavos": diferenca,
                "conciliado": diferenca == 0 and not divergencias["vendas_divergentes"],
                "aviso": (
                    "Conferência aritmética. Não representa confirmação bancária de PIX ou cartão."
                ),
            },
            "divergencias": divergencias,
            "pagamentos_pendentes": pendentes,
            "estoque": self.resumo_estoque(),
            "crediario_do_dia": self.crediario_do_dia(data_negocio),
            "escopo": (
                "Filtro: data comercial e status CONCLUIDA. Estoque e crediário são "
                "posições correntes e não reagem a este filtro de data."
            ),
        }

    def registrar_fechamento(self, *, data_negocio: str, usuario: Usuario) -> dict:
        usuario.exigir(Acao.FECHAMENTO_GERAR)
        agora = self.ctx.agora()
        relatorio = self.fechamento_dia(data_negocio)
        with self.ctx.em_transacao():
            fechamento_id = self.ctx.fechamentos.registrar(
                data_negocio=data_negocio,
                turno_id="",
                snapshot=relatorio,
                criado_em=agora,
                criado_por=usuario.id,
            )
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.FECHAMENTO_GERADO,
                    criado_em_utc=agora,
                    data_negocio=data_negocio,
                    ator_id=usuario.id,
                    entidade="fechamento",
                    entidade_id=fechamento_id,
                    depois={
                        "faturamento_centavos": relatorio["resumo"]["faturamento_centavos"],
                        "conciliado": relatorio["conciliacao"]["conciliado"],
                    },
                )
            )
        return {"fechamento_id": fechamento_id, "relatorio": relatorio}

    # -- indicadores --------------------------------------------------------
    def resumo_estoque(self) -> dict:
        indicadores = self.ctx.produtos.indicadores_estoque()
        contagem = {status.value: 0 for status in StatusEstoque}
        valor_custo = 0
        for item in indicadores:
            if not item["produto"].ativo:
                continue
            contagem[item["status"].value] += 1
            valor_custo += int(item["valor_custo_centavos"])
        return {
            "produtos_ativos": sum(contagem.values()),
            "por_status": contagem,
            "valor_custo_centavos": valor_custo,
            "escopo": "Posição corrente; não reage a filtros de data.",
        }

    def crediario_do_dia(self, data_negocio: str) -> dict:
        servico = ServicoCrediario(self.ctx)
        titulos = servico.listar()
        vencendo = [t for t in titulos if t["vencimento"] == data_negocio]
        return {
            "titulos_abertos": len(titulos),
            "saldo_aberto_centavos": sum(int(t["saldo_centavos"]) for t in titulos),
            "vencendo_hoje_centavos": sum(int(t["saldo_centavos"]) for t in vencendo),
            "escopo": "Posição corrente do crediário; não é filtrada pela data do fechamento.",
        }

    def dashboard(self, data_inicial: str, data_final: str, *, operador_id: str | None = None) -> dict:
        resumo = self.ctx.vendas.resumo_periodo(data_inicial, data_final, operador_id=operador_id)
        formas = self.ctx.vendas.por_forma(data_inicial, data_final, operador_id=operador_id)
        lucro_bruto = int(resumo["faturamento_centavos"]) - int(resumo["custo_centavos"])
        serie = [
            dict(linha)
            for linha in self.ctx.conexao.execute(
                """SELECT data_negocio, COUNT(*) AS cupons, SUM(total_centavos) AS total_centavos
                     FROM vendas WHERE status = 'CONCLUIDA' AND data_negocio BETWEEN ? AND ?
                    GROUP BY data_negocio ORDER BY data_negocio""",
                (data_inicial, data_final),
            )
        ]
        return {
            "periodo": {"inicio": data_inicial, "fim": data_final, "operador_id": operador_id},
            "resumo": resumo,
            "lucro_bruto_centavos": lucro_bruto,
            "margem_bruta_bp": (
                lucro_bruto * 10_000 // int(resumo["faturamento_centavos"])
                if resumo["faturamento_centavos"]
                else 0
            ),
            "por_forma": formas,
            "serie_diaria": serie,
            "estoque": self.resumo_estoque(),
            "aviso": "Lucro bruto estimado: não considera impostos, taxas de cartão nem despesas.",
        }
