"""Serviço de impressão: do dado do banco ao papel — ou ao arquivo, se não houver papel.

Regras que este módulo garante:

1. **A tela não monta texto de cupom.** Ela pede o `DocumentoImpresso` aqui, mostra
   a prévia e manda imprimir. Assim o cupom do PDV, o do recibo reimpresso e o PDF
   salvo têm o mesmo conteúdo, porque vêm da mesma função.
2. **Todo cupom é documento interno.** Não é nota fiscal, não substitui SAT/NFC-e e
   não confirma liquidação de PIX/cartão — o texto do aviso é parte do documento.
3. **Impressão deixa rastro.** Cada envio bem-sucedido grava `IMPRESSAO_REALIZADA`
   (qual documento, qual impressora, qual motor); falha grava `IMPRESSAO_FALHOU`.
   Sem isso, "saiu o cupom da venda 45?" vira discussão sem prova.
4. **Sem rede.** Nada aqui abre socket: ou o driver do sistema (spooler local/CUPS),
   ou bytes ESC/POS na fila local.
5. **Quando não há impressora, não se perde o cupom.** `salvar()` grava PDF ou TXT
   na pasta escolhida; a tela oferece isso no mesmo diálogo.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.dinheiro import Dinheiro, Quantidade
from ..dominio.erros import ErroImpressao, ErroNaoEncontrado, ErroValidacao
from ..dominio.impressao import (
    PERFIS_PAPEL,
    Alinhamento,
    Bloco,
    CodigoDeBarras,
    Divisor,
    DocumentoImpresso,
    Enfase,
    Item,
    Papel,
    Par,
    Texto,
    largura_de,
)
from ..dominio.marca import Marca
from ..dominio.pagamentos import FormaPagamento
from ..dominio.relatorio import DOCUMENTO_INTERNO, Relatorio, Tabela, TipoColuna
from ..dominio.usuario import Acao, Usuario
from ..infra.exportacao.formato import celula, data_br, moeda
from ..infra.impressao import escpos, impressoras
from ..infra.impressao import papel as renderizador_papel
from ..infra.impressao import texto as renderizador_texto
from ..infra.sqlite.repositorio_vendas import VendaRegistrada
from .contexto import Contexto
from .marca import ServicoMarca

#: Aviso que acompanha todo cupom: o projeto não emite documento fiscal.
AVISO_NAO_FISCAL = "Documento interno, não fiscal. Não substitui nota fiscal."

#: Abaixo disto uma coluna de tabela em papel não é legível (cabe "R$ 9,99" e pouco mais).
LARGURA_MINIMA_COLUNA = 7


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


class MotorImpressao(StrEnum):
    """Como os bytes chegam à impressora.

    * `SISTEMA` — pelo driver instalado (Windows spooler / CUPS). Funciona em
      qualquer impressora, inclusive térmica com driver próprio; é o padrão porque
      é o único que dispensa configuração.
    * `ESCPOS` — bytes crus na fila local. Necessário para corte automático,
      gaveta e código de barras nativo em térmicas compatíveis (Elgin, Bematech,
      Epson TM, POS-58/80). Exige bobina.
    """

    SISTEMA = "SISTEMA"
    ESCPOS = "ESCPOS"

    @property
    def rotulo(self) -> str:
        return {
            MotorImpressao.SISTEMA: "Driver do sistema (qualquer impressora)",
            MotorImpressao.ESCPOS: "ESC/POS direto (térmica: corte, gaveta, barras)",
        }[self]


@dataclass(frozen=True, slots=True)
class ConfiguracaoImpressao:
    """O que está configurado hoje, lido dos parâmetros (não do arquivo de tela)."""

    motor: MotorImpressao = MotorImpressao.SISTEMA
    impressora: str = ""
    papel: Papel = Papel.BOBINA_80
    copias: int = 1
    cortar_papel: bool = True
    abrir_gaveta: bool = False
    codigo_de_barras: bool = True
    imprimir_automatico: bool = False

    @property
    def motor_rotulo(self) -> str:
        return self.motor.rotulo

    @property
    def papel_rotulo(self) -> str:
        return PERFIS_PAPEL[self.papel].rotulo


@dataclass(frozen=True, slots=True)
class ResultadoImpressao:
    """O que aconteceu, para a tela poder contar ao operador."""

    titulo: str
    destino: str
    motor: MotorImpressao
    papel: Papel
    linhas: int
    copias: int
    via_arquivo: Path | None = None

    @property
    def resumo(self) -> str:
        alvo = self.impressora_ou_arquivo
        return f"{self.titulo} — {self.linhas} linha(s) em {self.papel.value} → {alvo}"

    @property
    def impressora_ou_arquivo(self) -> str:
        return str(self.via_arquivo) if self.via_arquivo else self.destino


class ServicoImpressao:
    """Monta documentos impressos e os entrega ao motor configurado."""

    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- configuração --------------------------------------------------------
    def configuracao(self) -> ConfiguracaoImpressao:
        motor_bruto = self.ctx.parametros.obter("impressao.motor").strip().upper()
        try:
            motor = MotorImpressao(motor_bruto)
        except ValueError:
            motor = MotorImpressao.SISTEMA
        papel_bruto = self.ctx.parametros.obter("impressao.papel").strip().upper()
        try:
            papel = Papel(papel_bruto)
        except ValueError:
            papel = Papel.BOBINA_80
        return ConfiguracaoImpressao(
            motor=motor,
            impressora=self.ctx.parametros.obter("impressao.impressora").strip(),
            papel=papel,
            copias=max(1, self.ctx.parametros.obter_int("impressao.copias")),
            cortar_papel=self.ctx.parametros.obter_bool("impressao.cortar_papel"),
            abrir_gaveta=self.ctx.parametros.obter_bool("impressao.abrir_gaveta"),
            codigo_de_barras=self.ctx.parametros.obter_bool("impressao.codigo_de_barras"),
            imprimir_automatico=self.ctx.parametros.obter_bool("impressao.imprimir_automatico"),
        )

    def impressora_efetiva(self, configuracao: ConfiguracaoImpressao | None = None) -> str:
        """Impressora configurada; vazia cai na padrão do sistema."""
        cfg = configuracao or self.configuracao()
        return cfg.impressora or impressoras.padrao()

    # -- identidade da loja --------------------------------------------------
    def _marca(self) -> Marca | None:
        try:
            return ServicoMarca(self.ctx).obter()
        except Exception:  # pragma: no cover - base recém-criada não tem marca
            return None

    def _cabecalho(self, marca: Marca | None, *, titulo: str) -> list[Bloco]:
        """Blocos de topo: nome da loja, contato e identificação do documento."""
        blocos: list[Bloco] = []
        if marca is not None:
            blocos.append(Texto(marca.nome_fantasia, Alinhamento.CENTRO, Enfase.TITULO))
            for linha in self._contato_da_loja(marca):
                blocos.append(Texto(linha, Alinhamento.CENTRO))
        blocos.append(Divisor("="))
        blocos.append(Texto(titulo, Alinhamento.CENTRO, Enfase.FORTE))
        blocos.append(Divisor("="))
        return blocos

    def _contato_da_loja(self, marca: Marca) -> list[str]:
        """Linhas de contato que existem de fato — cupom sem CNPJ em branco."""
        candidatas = [
            marca.razao_social,
            f"CNPJ {marca.cnpj}" if marca.cnpj else "",
            marca.endereco,
            f"Tel. {marca.telefone}" if marca.telefone else "",
        ]
        return [linha.strip() for linha in candidatas if linha.strip()]

    def _rodape(self, marca: Marca | None, *, extra: tuple[str, ...] = ()) -> list[Bloco]:
        """Avisos do fim do papel, sem repetir o mesmo aviso três vezes.

        Os relatórios já trazem o próprio "documento interno, não fiscal" no rodapé
        que vem da exportação; somar o aviso padrão em cima disso imprimia três
        linhas quase iguais e comia bobina. A regra é simples: aviso repetido sai,
        e o aviso padrão só entra se nenhum outro já falar de documento fiscal.
        """
        blocos: list[Bloco] = [Divisor("=")]
        if marca is not None and marca.rodape_comprovante.strip():
            blocos.append(Texto(marca.rodape_comprovante.strip(), Alinhamento.CENTRO))
        vistos: list[str] = []
        for aviso in extra:
            limpo = aviso.strip()
            normalizado = _sem_acento(limpo.lower())
            if not limpo or any(normalizado in visto or visto in normalizado for visto in vistos):
                continue
            vistos.append(normalizado)
            blocos.append(Texto(limpo, Alinhamento.CENTRO))
        if not any("fiscal" in visto for visto in vistos):
            blocos.append(Texto(AVISO_NAO_FISCAL, Alinhamento.CENTRO, Enfase.NORMAL))
        return blocos

    # -- cupom de venda ------------------------------------------------------
    def comprovante_da_venda(
        self,
        venda: VendaRegistrada,
        *,
        papel: Papel | None = None,
        configuracao: ConfiguracaoImpressao | None = None,
        copia: bool = False,
    ) -> DocumentoImpresso:
        """Cupom da venda a partir do que está gravado no banco (não do carrinho).

        Ler do banco é o que garante que a **reimpressão** saia igual à primeira via:
        o carrinho já foi limpo, o preço pode ter mudado depois, e o cupom precisa
        mostrar o que foi efetivamente cobrado.
        """
        cfg = configuracao or self.configuracao()
        perfil = PERFIS_PAPEL[papel or cfg.papel]
        marca = self._marca()
        titulo = "COMPROVANTE DE VENDA" if not copia else "COMPROVANTE DE VENDA (2ª VIA)"
        blocos: list[Bloco] = self._cabecalho(marca, titulo=titulo)

        blocos.append(Par("Cupom", venda.rotulo, Enfase.FORTE))
        blocos.append(Par("Data", self._data_hora(venda)))
        operador = self._nome_do_operador(venda.operador_id)
        if operador:
            blocos.append(Par("Operador", operador))
        cliente = self._nome_do_cliente(venda.cliente_id)
        if cliente:
            blocos.append(Par("Cliente", cliente))
        if venda.status.value != "CONCLUIDA":
            blocos.append(Texto(f"*** VENDA {venda.status.value} ***", Alinhamento.CENTRO, Enfase.FORTE))
        blocos.append(Divisor())

        itens = self.ctx.vendas.itens(venda.id)
        for linha in itens:
            blocos.append(
                Item(
                    descricao=str(linha["descricao"]),
                    quantidade=Quantidade(int(linha["quantidade_milesimos"])),
                    unidade=str(linha["unidade"]),
                    unitario=Dinheiro(int(linha["preco_unitario_centavos"])),
                    total=Dinheiro(int(linha["total_centavos"])),
                    desconto=Dinheiro(int(linha["desconto_centavos"])),
                    codigo=str(linha["codigo_produto"]),
                )
            )
        blocos.append(Divisor())

        if venda.subtotal.centavos != venda.total.centavos or venda.desconto.centavos:
            blocos.append(Par("Subtotal", venda.subtotal.formatado()))
        if venda.desconto.centavos:
            blocos.append(Par("Desconto", f"-{venda.desconto.formatado()}"))
        if venda.acrescimo.centavos:
            blocos.append(Par("Acréscimo", venda.acrescimo.formatado()))
        blocos.append(Par("TOTAL", venda.total.formatado(), Enfase.TITULO))

        pagamentos = self.ctx.vendas.pagamentos(venda.id)
        if pagamentos:
            blocos.append(Divisor("."))
            for linha in pagamentos:
                forma = FormaPagamento(str(linha["forma"]))
                valor = Dinheiro(int(linha["valor_aplicado_centavos"]))
                blocos.append(Par(forma.rotulo, valor.formatado()))
                if int(linha["troco_centavos"]):
                    blocos.append(Par("  Troco", Dinheiro(int(linha["troco_centavos"])).formatado()))
                if str(linha["status"]) != "CONFIRMADO" and forma.eletronico:
                    blocos.append(
                        Texto(
                            f"  {forma.rotulo}: {linha['status']} — confira na maquininha",
                            Alinhamento.ESQUERDA,
                        )
                    )
        blocos.append(Divisor("."))

        avisos: list[str] = []
        if perfil.colunas >= 40:
            avisos.append(f"Documento gerado pelo Bússola PDV em {self._agora_legivel()}.")
        if cfg.codigo_de_barras:
            # CODE 39 do rótulo: a leitora da loja reabre o cupom pelo número.
            blocos.append(CodigoDeBarras(venda.rotulo))
        blocos.extend(self._rodape(marca, extra=tuple(avisos)))
        return DocumentoImpresso(
            titulo=titulo,
            papel=perfil.papel,
            blocos=tuple(blocos),
            rotulo=f"cupom-{venda.rotulo}",
        )

    def venda_por_referencia(self, referencia: str) -> VendaRegistrada:
        """Aceita o id da venda, o rótulo do cupom (`1-000012`) ou o número (`12`).

        Existe para a CLI e o suporte: quem liga não sabe o UUID, sabe o número que
        está impresso no papel.
        """
        texto = str(referencia).strip().removeprefix("cupom:").strip()
        if not texto:
            raise ErroValidacao("Informe a venda (id ou rótulo do cupom).")
        try:
            return self.ctx.vendas.por_id(texto)
        except ErroNaoEncontrado:
            return self.ctx.vendas.por_rotulo(texto)

    def comprovante_por_id(
        self, venda_id: str, *, papel: Papel | None = None, copia: bool = True
    ) -> DocumentoImpresso:
        """Reimpressão: busca a venda pelo id e monta o cupom marcado como 2ª via."""
        venda = self.ctx.vendas.por_id(venda_id)
        return self.comprovante_da_venda(venda, papel=papel, copia=copia)

    # -- relatórios (turno, fechamento) --------------------------------------
    def documento_de_relatorio(
        self,
        relatorio: Relatorio,
        *,
        papel: Papel | None = None,
        rotulo: str = "relatorio",
    ) -> DocumentoImpresso:
        """Relatório → documento impresso, no papel pedido.

        Em **A4** as tabelas saem como tabela de verdade (colunas proporcionais).
        Em **bobina** a tabela vira pares rótulo/valor — em 32 colunas uma tabela de
        quatro colunas fica ilegível, e cupom de conferência se lê de cima para baixo.
        """
        cfg = self.configuracao()
        perfil = PERFIS_PAPEL[papel or cfg.papel]
        marca = self._marca()
        blocos: list[Bloco] = self._cabecalho(marca, titulo=relatorio.titulo.upper())
        if relatorio.subtitulo:
            blocos.append(Texto(relatorio.subtitulo, Alinhamento.CENTRO))
        for rotulo_item, valor in (*relatorio.identificacao, *relatorio.filtros):
            blocos.append(Par(rotulo_item, valor))
        if relatorio.indicadores:
            blocos.append(Divisor())
            for rotulo_item, valor in relatorio.indicadores:
                blocos.append(Par(rotulo_item, valor))
        for tabela in relatorio.tabelas:
            blocos.append(Divisor())
            blocos.append(Texto(tabela.titulo, Alinhamento.CENTRO, Enfase.FORTE))
            blocos.extend(self._linhas_da_tabela(tabela, perfil.colunas))
            if tabela.nota:
                blocos.append(Texto(tabela.nota, Alinhamento.ESQUERDA))
        avisos = tuple(relatorio.avisos) + ((relatorio.documento,) if relatorio.documento else ())
        blocos.extend(self._rodape(marca, extra=avisos))
        return DocumentoImpresso(
            titulo=relatorio.titulo,
            papel=perfil.papel,
            blocos=tuple(blocos),
            rotulo=rotulo,
        )

    def _linhas_da_tabela(self, tabela: Tabela, colunas: int) -> list[Bloco]:
        """Tabela → blocos, decidindo pela **viabilidade**, não pela largura do papel.

        A grade só vale se cada célula couber na coluna que lhe cabe. Antes o
        critério era "menos de 40 colunas usa pares", e isso produzia bobina de
        80 mm com `R$ 30,…` — valor monetário cortado é pior que tabela feia.
        Agora: cabe tudo → grade; não cabe → pares rótulo/valor.
        """
        if tabela.vazia:
            return [Texto("(sem registros)", Alinhamento.CENTRO)]
        if not self._cabe_em_grade(tabela, colunas):
            return [self._par_da_linha(tabela, linha) for linha in tabela.linhas]
        return self._tabela_em_colunas(tabela, colunas)

    @staticmethod
    def _par_da_linha(tabela: Tabela, linha: tuple[object, ...]) -> Par:
        """Linha de tabela vira `rótulo · rótulo   valor` na bobina.

        O valor é a **última coluna numérica** (é o que interessa em cupom de
        conferência); as demais viram rótulo, sem os campos vazios. Sem essa
        escolha, a última coluna de uma tabela (autorizador, motivo) empurrava o
        dinheiro para o meio da linha — e "R$ 30,00" aparecia como rótulo.
        """
        valores = [
            celula(valor, coluna.tipo).strip()
            for coluna, valor in zip(tabela.colunas, linha, strict=False)
        ]
        numericas = [i for i, coluna in enumerate(tabela.colunas) if coluna.numerica]
        indice_valor = numericas[-1] if numericas else len(valores) - 1
        rotulo = " · ".join(
            valor
            for indice, valor in enumerate(valores)
            if indice != indice_valor and valor and valor != "—"
        )
        return Par(rotulo or "—", valores[indice_valor])

    def _cabe_em_grade(self, tabela: Tabela, colunas: int) -> bool:
        """Grade quando o que **não pode** ser cortado cabe; senão, pares.

        A distinção é deliberada: `R$ 1.234,56` truncado é dado errado, enquanto
        nome de produto comprido pode ser elidido com `…` sem prejuízo. Então a
        grade exige que cabeçalho, dinheiro, quantidade e data caibam inteiros; só
        as colunas de texto aceitam corte.
        """
        larguras = self._larguras_da_tabela(tabela, colunas)
        for indice, largura in enumerate(larguras):
            coluna = tabela.colunas[indice]
            if largura_de(coluna.titulo) > largura:
                return False
            if coluna.tipo is TipoColuna.TEXTO:
                continue
            for linha in tabela.linhas:
                if largura_de(celula(linha[indice], coluna.tipo)) > largura:
                    return False
        return True

    @staticmethod
    def _larguras_da_tabela(tabela: Tabela, colunas: int) -> list[int]:
        """Divide a largura do papel na proporção das colunas declaradas."""
        declaradas = sum(max(coluna.largura, LARGURA_MINIMA_COLUNA) for coluna in tabela.colunas)
        larguras = [
            max(
                LARGURA_MINIMA_COLUNA,
                round(max(coluna.largura, LARGURA_MINIMA_COLUNA) * colunas / max(declaradas, 1)),
            )
            for coluna in tabela.colunas
        ]
        sobra = colunas - sum(larguras)
        if sobra:
            larguras[-1] += sobra
        return larguras

    def _tabela_em_colunas(self, tabela: Tabela, colunas: int) -> list[Bloco]:
        """Grade de largura fixa: cabeçalho, régua e linhas.

        Chega aqui só o que `_cabe_em_grade` aprovou; o corte com `…` fica como
        rede de segurança para nomes longos de produto, não para valores.
        """
        larguras = self._larguras_da_tabela(tabela, colunas)

        def montar(valores: list[str]) -> str:
            celulas = [
                _ajustar(texto, largura, coluna)
                for texto, largura, coluna in zip(valores, larguras, tabela.colunas, strict=False)
            ]
            return " ".join(celulas).rstrip()

        blocos: list[Bloco] = [
            Texto(montar([coluna.titulo for coluna in tabela.colunas]), Alinhamento.ESQUERDA, Enfase.FORTE),
            Divisor("-"),
        ]
        for linha in tabela.linhas:
            valores = [
                celula(valor, coluna.tipo)
                for coluna, valor in zip(tabela.colunas, linha, strict=False)
            ]
            blocos.append(Texto(montar(valores)))
        return blocos

    # -- entrega -------------------------------------------------------------
    def despachar(
        self,
        documento: DocumentoImpresso,
        *,
        ator: Usuario | None = None,
        configuracao: ConfiguracaoImpressao | None = None,
        permissao: Acao = Acao.CUPOM_REIMPRIMIR,
    ) -> ResultadoImpressao:
        """Imprime pelo motor configurado e registra o resultado na auditoria.

        A permissão é conferida **aqui**, não só na tela: botão escondido não é
        controle de acesso, e a mesma chamada pode vir da CLI ou de um teste.

        `permissao` existe porque imprimir **cupom** e imprimir **relatório** não
        são a mesma coisa: cupom é operação de balcão (`CUPOM_REIMPRIMIR`, que o
        atendente tem); relatório é tirar dado da loja (`EXPORTAR_DADOS`, que ele
        não tem).
        """
        if ator is not None:
            ator.exigir(permissao)
        cfg = configuracao or self.configuracao()
        destino = self.impressora_efetiva(cfg)
        try:
            if cfg.motor is MotorImpressao.ESCPOS:
                self._enviar_espos(documento, destino, cfg)
            else:
                renderizador_papel.imprimir(documento, destino, copias=cfg.copias)
        except ErroImpressao as erro:
            self._auditar(
                AcaoAuditoria.IMPRESSAO_FALHOU,
                ator,
                documento,
                cfg,
                destino,
                extra={"motivo": erro.mensagem, "codigo": erro.codigo},
            )
            raise
        resultado = ResultadoImpressao(
            titulo=documento.titulo,
            destino=destino,
            motor=cfg.motor,
            papel=documento.papel,
            linhas=len(documento.layout()),
            copias=cfg.copias,
        )
        self._auditar(AcaoAuditoria.IMPRESSAO_REALIZADA, ator, documento, cfg, destino)
        return resultado

    def _enviar_espos(
        self, documento: DocumentoImpresso, destino: str, cfg: ConfiguracaoImpressao
    ) -> None:
        if not documento.papel.value.startswith("BOBINA"):
            raise ErroValidacao(
                "O motor ESC/POS imprime bobina (58 mm ou 80 mm). Para folha A4, "
                "use o motor SISTEMA ou salve em PDF."
            )
        for _ in range(cfg.copias):
            dados = escpos.renderizar(
                documento, abrir_gaveta=cfg.abrir_gaveta, cortar=cfg.cortar_papel
            )
            impressoras.enviar_bytes(destino, dados)

    def salvar(
        self,
        documento: DocumentoImpresso,
        pasta: Path,
        *,
        formato: str = "pdf",
    ) -> Path:
        """Grava o documento na pasta escolhida — plano B quando não há impressora."""
        pasta = Path(pasta)
        if formato.lower() == "txt":
            destino = pasta / f"{documento.rotulo}.txt"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(renderizador_texto.renderizar(documento), encoding="utf-8")
            return destino
        if formato.lower() not in ("pdf", ""):
            raise ErroValidacao(f"Formato de impressão desconhecido: {formato!r}. Use pdf ou txt.")
        return renderizador_papel.escrever_pdf(documento, pasta / f"{documento.rotulo}.pdf")

    # -- auxiliares ----------------------------------------------------------
    def _auditar(
        self,
        acao: AcaoAuditoria,
        ator: Usuario | None,
        documento: DocumentoImpresso,
        cfg: ConfiguracaoImpressao,
        destino: str,
        *,
        extra: dict | None = None,
    ) -> None:
        if ator is None:
            return
        agora = self.ctx.agora()
        depois: dict = {
            "documento": documento.titulo,
            "rotulo": documento.rotulo,
            "papel": documento.papel.value,
            "motor": cfg.motor.value,
            "impressora": destino,
            "linhas": len(documento.layout()),
            "copias": cfg.copias,
        }
        if extra:
            depois.update(extra)
        self.ctx.auditoria.registrar(
            EventoAuditoria(
                acao=acao,
                criado_em_utc=agora,
                data_negocio=self.ctx.relogio.data_negocio(),
                ator_id=ator.id,
                entidade="impressao",
                entidade_id=documento.rotulo,
                depois=depois,
                motivo=f"Impressão de {documento.titulo}",
            )
        )

    def _data_hora(self, venda: VendaRegistrada) -> str:
        try:
            return venda.criado_em.astimezone().strftime("%d/%m/%Y %H:%M")
        except (AttributeError, ValueError):  # pragma: no cover - data já local
            return venda.data_negocio

    def _agora_legivel(self) -> str:
        return self.ctx.agora().strftime("%d/%m/%Y %H:%M")

    def _nome_do_operador(self, operador_id: str) -> str:
        try:
            return self.ctx.usuarios.por_id(operador_id).nome
        except Exception:  # pragma: no cover - operador removido da base
            return ""

    def _nome_do_cliente(self, cliente_id: str | None) -> str:
        if not cliente_id:
            return ""
        try:
            return self.ctx.clientes.por_id(cliente_id).nome
        except Exception:  # pragma: no cover - cliente removido da base
            return ""


def _ajustar(texto: str, largura: int, coluna: object) -> str:
    """Encaixa a célula na coluna: número à direita, texto à esquerda, corte com `…`."""
    tipo = getattr(coluna, "tipo", TipoColuna.TEXTO)
    valor = texto if largura_de(texto) <= largura else _encurtar(texto, largura)
    if tipo in (TipoColuna.MOEDA, TipoColuna.INTEIRO):
        return valor.rjust(largura)
    return valor.ljust(largura)


def _encurtar(texto: str, largura: int) -> str:
    if largura <= 1:
        return texto[:1]
    while largura_de(texto) > largura - 1 and texto:
        texto = texto[:-1]
    return texto + "…"


__all__ = [
    "AVISO_NAO_FISCAL",
    "DOCUMENTO_INTERNO",
    "ConfiguracaoImpressao",
    "MotorImpressao",
    "ResultadoImpressao",
    "ServicoImpressao",
    "data_br",
    "moeda",
]
