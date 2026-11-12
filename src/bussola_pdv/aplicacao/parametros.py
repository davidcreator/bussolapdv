"""Parâmetros de operação editáveis na área administrativa.

Cada parâmetro tem tipo, faixa e descrição declarados aqui — a tela não inventa
validação. Alteração exige `PARAMETRO_ALTERAR` e entra na trilha de auditoria
com valor anterior e posterior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.erros import ErroValidacao
from ..dominio.usuario import Acao, Usuario
from .contexto import Contexto


class TipoParametro(StrEnum):
    INTEIRO = "INTEIRO"
    BOOLEANO = "BOOLEANO"
    TEXTO = "TEXTO"
    PERCENTUAL = "PERCENTUAL"  # exibido em %, armazenado em pontos-base
    OPCAO = "OPCAO"  # lista fechada de valores (ex.: motor de impressão)

    @property
    def rotulo(self) -> str:
        return {
            TipoParametro.INTEIRO: "número inteiro",
            TipoParametro.BOOLEANO: "sim/não",
            TipoParametro.TEXTO: "texto",
            TipoParametro.PERCENTUAL: "percentual",
            TipoParametro.OPCAO: "uma das opções da lista",
        }[self]


@dataclass(frozen=True, slots=True)
class DefinicaoParametro:
    chave: str
    grupo: str
    rotulo: str
    tipo: TipoParametro
    ajuda: str = ""
    minimo: int | None = None
    maximo: int | None = None
    unidade: str = ""
    #: Valores aceitos quando `tipo` é `OPCAO`; a tela monta a lista a partir daqui.
    opcoes: tuple[str, ...] = ()
    #: TEXTO que pode ficar vazio (ex.: "usar a impressora padrão do sistema").
    permite_vazio: bool = False


#: Catálogo fechado. Chave fora daqui não é editável pela interface.
DEFINICOES: tuple[DefinicaoParametro, ...] = (
    DefinicaoParametro(
        "operacao.modo",
        "Operação",
        "Modo de operação",
        TipoParametro.TEXTO,
        "Use TESTE enquanto os dados forem fictícios.",
    ),
    DefinicaoParametro(
        "operacao.fuso", "Operação", "Fuso horário", TipoParametro.TEXTO,
        "Fuso usado para a data comercial (ex.: America/Sao_Paulo).",
    ),
    DefinicaoParametro(
        "desconto.limite_operador_bp",
        "Descontos",
        "Desconto máximo do atendente",
        TipoParametro.PERCENTUAL,
        "Acima disso, exige autorização registrada.",
        minimo=0,
        maximo=10_000,
    ),
    DefinicaoParametro(
        "desconto.limite_gerente_bp",
        "Descontos",
        "Desconto máximo com gerente",
        TipoParametro.PERCENTUAL,
        "Usado na autorização por senha de um segundo usuário.",
        minimo=0,
        maximo=10_000,
    ),
    DefinicaoParametro(
        "desconto.limite_maximo_bp",
        "Descontos",
        "Teto absoluto de desconto",
        TipoParametro.PERCENTUAL,
        "Nenhuma venda passa disso, nem com autorização.",
        minimo=0,
        maximo=10_000,
    ),
    DefinicaoParametro(
        "venda.exigir_confirmacao_eletronica",
        "Vendas",
        "Exigir confirmação de PIX/cartão",
        TipoParametro.BOOLEANO,
        "Ligado: a venda não finaliza com pagamento eletrônico pendente.",
    ),
    DefinicaoParametro(
        "crediario.maximo_parcelas",
        "Crediário",
        "Máximo de parcelas",
        TipoParametro.INTEIRO,
        "Limite do sistema: 48.",
        minimo=1,
        maximo=48,
    ),
    DefinicaoParametro(
        "crediario.dias_bloqueio_atraso",
        "Crediário",
        "Dias de atraso para bloquear",
        TipoParametro.INTEIRO,
        "A partir daqui o cliente fica impedido de comprar a prazo.",
        minimo=0,
        maximo=365,
        unidade="dias",
    ),
    DefinicaoParametro(
        "caixa.limite_diferenca_centavos",
        "Caixa",
        "Tolerância de diferença no fechamento",
        TipoParametro.INTEIRO,
        "Em centavos. Acima disso a diferença é classificada como fora do limite.",
        minimo=0,
        maximo=100_000,
        unidade="centavos",
    ),
    DefinicaoParametro(
        "impressao.motor",
        "Impressão",
        "Motor de impressão",
        TipoParametro.OPCAO,
        "SISTEMA usa o driver instalado e serve qualquer impressora. "
        "ESCPOS manda bytes diretos: corte automático, gaveta e código de barras "
        "nativo, mas exige impressora térmica compatível e bobina.",
        opcoes=("SISTEMA", "ESCPOS"),
    ),
    DefinicaoParametro(
        "impressao.impressora",
        "Impressão",
        "Impressora",
        TipoParametro.TEXTO,
        "Nome exato como aparece no Windows (Dispositivos e impressoras). "
        "Em branco, o sistema usa a impressora padrão.",
        permite_vazio=True,
    ),
    DefinicaoParametro(
        "impressao.papel",
        "Impressão",
        "Papel",
        TipoParametro.OPCAO,
        "BOBINA_58 e BOBINA_80 são bobinas de térmica; A4 é folha comum. "
        "O papel define quantas colunas o cupom tem e o que cabe na linha.",
        opcoes=("BOBINA_58", "BOBINA_80", "A4"),
    ),
    DefinicaoParametro(
        "impressao.copias",
        "Impressão",
        "Cópias por documento",
        TipoParametro.INTEIRO,
        "Aplicado no driver e no motor ESC/POS.",
        minimo=1,
        maximo=5,
        unidade="via(s)",
    ),
    DefinicaoParametro(
        "impressao.cortar_papel",
        "Impressão",
        "Cortar o papel ao fim do cupom",
        TipoParametro.BOOLEANO,
        "Só no motor ESC/POS; depende de a térmica ter guilhotina.",
    ),
    DefinicaoParametro(
        "impressao.abrir_gaveta",
        "Impressão",
        "Abrir a gaveta ao imprimir",
        TipoParametro.BOOLEANO,
        "Só no motor ESC/POS e com a gaveta ligada na porta da impressora.",
    ),
    DefinicaoParametro(
        "impressao.codigo_de_barras",
        "Impressão",
        "Imprimir código de barras do cupom",
        TipoParametro.BOOLEANO,
        "CODE 39 com o número do cupom (ex.: 1-000012), para reler o cupom.",
    ),
    DefinicaoParametro(
        "impressao.imprimir_automatico",
        "Impressão",
        "Imprimir o cupom ao finalizar a venda",
        TipoParametro.BOOLEANO,
        "Desligado, o operador confirma na janela de pré-visualização antes de imprimir.",
    ),
    DefinicaoParametro(
        "seguranca.maximo_tentativas",
        "Segurança",
        "Tentativas de login antes do bloqueio",
        TipoParametro.INTEIRO,
        minimo=3,
        maximo=20,
    ),
    DefinicaoParametro(
        "seguranca.bloqueio_minutos",
        "Segurança",
        "Minutos de bloqueio",
        TipoParametro.INTEIRO,
        minimo=1,
        maximo=1440,
        unidade="minutos",
    ),
)

POR_CHAVE = {definicao.chave: definicao for definicao in DEFINICOES}


class ServicoParametros:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    def listar(self) -> list[tuple[DefinicaoParametro, str]]:
        valores = self.ctx.parametros.todos()
        return [(definicao, valores.get(definicao.chave, "")) for definicao in DEFINICOES]

    def grupos(self) -> dict[str, list[tuple[DefinicaoParametro, str]]]:
        agrupado: dict[str, list[tuple[DefinicaoParametro, str]]] = {}
        for definicao, valor in self.listar():
            agrupado.setdefault(definicao.grupo, []).append((definicao, valor))
        return agrupado

    def obter_exibicao(self, definicao: DefinicaoParametro) -> str:
        bruto = self.ctx.parametros.obter(definicao.chave)
        if definicao.tipo is TipoParametro.PERCENTUAL:
            return f"{int(bruto) / 100:.2f}".replace(".", ",")
        if definicao.tipo is TipoParametro.BOOLEANO:
            return "Sim" if bruto.strip() in {"1", "true", "True", "S", "SIM"} else "Não"
        return bruto

    def validar(self, definicao: DefinicaoParametro, texto: str) -> str:
        """Converte o que o usuário digitou no valor persistido, ou explica o erro."""
        limpo = texto.strip()
        if definicao.tipo is TipoParametro.OPCAO:
            valor = limpo.upper()
            if valor not in definicao.opcoes:
                raise ErroValidacao(
                    f"{definicao.rotulo} deve ser uma destas opções: "
                    f"{', '.join(definicao.opcoes)}."
                )
            return valor
        if definicao.tipo is TipoParametro.TEXTO:
            if not limpo and not definicao.permite_vazio:
                raise ErroValidacao(f"{definicao.rotulo} não pode ficar vazio.")
            return limpo
        if definicao.tipo is TipoParametro.BOOLEANO:
            return "1" if limpo.lower() in {"1", "sim", "s", "true", "ligado"} else "0"
        if definicao.tipo is TipoParametro.PERCENTUAL:
            numero = self._inteiro(limpo.replace("%", "").replace(",", "."), definicao, fracionario=True)
            pontos_base = round(numero * 100)
            if definicao.minimo is not None and pontos_base < definicao.minimo:
                raise ErroValidacao(f"{definicao.rotulo} abaixo do mínimo permitido.")
            if definicao.maximo is not None and pontos_base > definicao.maximo:
                raise ErroValidacao(f"{definicao.rotulo} acima do máximo permitido.")
            return str(pontos_base)
        numero = self._inteiro(limpo, definicao)
        if definicao.minimo is not None and numero < definicao.minimo:
            raise ErroValidacao(
                f"{definicao.rotulo} deve ser no mínimo {definicao.minimo}."
            )
        if definicao.maximo is not None and numero > definicao.maximo:
            raise ErroValidacao(
                f"{definicao.rotulo} deve ser no máximo {definicao.maximo}."
            )
        return str(numero)

    @staticmethod
    def _inteiro(texto: str, definicao: DefinicaoParametro, fracionario: bool = False) -> int | float:
        try:
            return float(texto) if fracionario else int(texto)
        except ValueError as exc:
            raise ErroValidacao(
                f"{definicao.rotulo} deve ser {definicao.tipo.rotulo}."
            ) from exc

    def definir(self, ator: Usuario, chave: str, texto: str) -> dict[str, object]:
        ator.exigir(Acao.PARAMETRO_ALTERAR)
        definicao = POR_CHAVE.get(chave)
        if definicao is None:
            raise ErroValidacao(f"Parâmetro não editável: {chave}")
        novo = self.validar(definicao, texto)
        anterior = self.ctx.parametros.obter(chave)
        if anterior == novo:
            return {"alterado": False, "chave": chave, "valor": novo}
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.parametros.definir(chave, novo, agora_iso=agora.isoformat())
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.PARAMETRO_ALTERADO,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=ator.id,
                    entidade="parametro",
                    entidade_id=chave,
                    antes={"valor": anterior},
                    depois={"valor": novo},
                    motivo=f"Alteração de {definicao.rotulo}",
                )
            )
        return {"alterado": True, "chave": chave, "valor": novo, "anterior": anterior}
