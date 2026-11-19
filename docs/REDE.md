# Vários caixas na mesma base (rede)

> **Status nesta versão:** a **API local** existe e está testada
> (`docs/API.md`), mas o programa ainda é **um caixa por base** (pendência P2).
> Este documento é o caminho acordado — servidor central + terminais — e o que
> falta para chegar lá, em ordem.

## 1. Por que não "SQLite numa pasta de rede"

O caminho mais óbvio (e o mais errado) é compartilhar `bussola.db` numa pasta de rede
e abrir o mesmo arquivo de dois computadores. Não funciona:

- o bloqueio de escrita do SQLite (`-wal`, `-shm`) depende do **sistema de arquivos**;
  SMB/NFS não garantem as travas — o resultado é corrupção silenciosa, não erro;
- duas estações gravando a mesma venda, o mesmo turno e o mesmo número sequencial
  geram duplicidade que a auditoria detecta **depois** do estrago;
- qualquer queda de rede no meio de uma transação deixa o arquivo em estado ambíguo.

O programa já avisa isso no README e no manual. Não é limitação temporária: é
propriedade do modelo de arquivo.

## 2. Arquitetura escolhida: servidor central + terminais

```
┌────────────────────┐        HTTP + token        ┌──────────────────────────┐
│ Terminal do balcão │ ─────────────────────────▶ │  Servidor (uma máquina)  │
│  tela Qt (cliente) │ ◀───────────────────────── │  API  +  bussola.db      │
└────────────────────┘                            └──────────────────────────┘
┌────────────────────┐                                     │
│ Segundo terminal   │ ────────────────────────────────────┘
└────────────────────┘                        backup local + cópia na nuvem
```

- **uma base só**, no servidor — a fonte da verdade é única, como hoje;
- cada terminal é **cliente**: a tela continua igual, o que muda é onde a operação é
  executada;
- o servidor pode ser a máquina do escritório da ONG, uma VM na AWS/Azure
  (`docs/NUVEM.md`) ou um mini-PC na loja;
- se a rede cair, o terminal **avisa e não vende** (melhor do que vender em base
  paralela e descobrir a divergência no fechamento).

## 3. O que já existe (v0.13.0)

| Peça | Estado |
|---|---|
| API HTTP com rotas de leitura (produtos, estoque, vendas, crediário, relatórios) | ✅ `docs/API.md` |
| Devolução e cancelamento pela API, com login/senha do operador e do autorizador | ✅ |
| Token por aplicação + credenciais por operação | ✅ |
| Contexto por thread (conexão SQLite nunca atravessa thread) | ✅ |
| Escuta em `127.0.0.1` por padrão | ✅ (abrir é decisão explícita) |

## 4. O que falta, em ordem

1. **Modo servidor explícito**: `api --host 0.0.0.0` já é aceito, mas hoje sem TLS.
   Antes de usar em rede: TLS terminado em **proxy reverso** (Caddy/Nginx) na mesma
   máquina, com certificado interno, e a API só em `127.0.0.1`.
2. **Rotas de escrita completas**: finalizar venda, abrir/fechar turno, receber título
   e lançar entrada ainda acontecem **só na tela** — são as próximas rotas.
3. **Identidade de terminal**: coluna `terminal_id` em `vendas`, `turnos` e
   auditoria, para responder "qual caixa fez isso".
4. **Turno por caixa** (já existe) + **fechamento por terminal** no fechamento do dia.
5. **Tela cliente**: o `JanelaPrincipal` de hoje abre o banco direto; precisa de um
   "modo remoto" que fale a API em vez de abrir o arquivo. É a maior parte do trabalho.
6. **Resiliência**: timeout, retry idempotente (a venda já tem chave de idempotência)
   e mensagem de erro que o operador entenda ("servidor sem resposta: chame quem cuida
   do computador").
7. **Teste de concorrência**: dois terminais vendendo ao mesmo tempo, com estoque
   disputado — automatizado, senão não vale.

Ordem de grandeza: **3 a 5 semanas** para um modo servidor utilizável, com um
terminal cliente; mais tempo se a loja quiser cair-e-voltar (réplica local).

## 5. Alternativa descartada por ora: réplica por caixa

Cada caixa com SQLite próprio, sincronizando eventos quando há rede. Funciona com
internet instável, mas custa caro: conflito de estoque, resolução de duplicidade,
relógios diferentes e o mesmo problema de "dois donos do número da venda". Só entra
se a loja tiver **rede instável e vendas simultâneas** — e, nesse caso, a decisão tem
que ser tomada antes, porque muda o modelo de dados.

## 6. Segurança mínima para ligar em rede

- TLS obrigatório (o token viaja no cabeçalho);
- um token por terminal, guardado em variável de ambiente da máquina;
- firewall liberando **só** a porta do proxy, e só para a faixa da loja;
- log de acesso na API (hoje silencioso de propósito, no modo local);
- backup do servidor: local **e** na nuvem (`docs/NUVEM.md`), com restauração testada.
