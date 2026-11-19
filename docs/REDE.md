# Vários caixas na mesma base (rede)

> **Status na v0.14.0:** o **modo servidor está pronto e testado** — API com todas
> as rotas de operação, TLS com certificado gerado pelo programa, identidade de
> terminal, log de acesso e teste de dois caixas vendendo ao mesmo tempo.
> O que **ainda não existe** é a tela do balcão conversando com o servidor: hoje o
> programa abre a base direto (um caixa por máquina). A ordem do que falta está na
> seção 4.

## 1. Por que não "SQLite numa pasta de rede"

O caminho mais óbvio (e o mais errado) é compartilhar `bussola.db` numa pasta de rede
e abrir o mesmo arquivo de dois computadores. Não funciona:

- o bloqueio de escrita do SQLite (`-wal`, `-shm`) depende do **sistema de arquivos**;
  SMB/NFS não garantem as travas — o resultado é corrupção silenciosa, não erro;
- duas estações gravando a mesma venda, o mesmo turno e o mesmo número sequencial
  geram duplicidade que a auditoria detecta **depois** do estrago;
- qualquer queda de rede no meio de uma transação deixa o arquivo em estado ambíguo.

O programa avisa isso no README e no manual. Não é limitação temporária: é
propriedade do modelo de arquivo.

## 2. Arquitetura escolhida: servidor central + terminais

```
┌────────────────────┐    HTTPS + token + X-Bussola-Terminal   ┌──────────────────────────┐
│ Terminal do balcão │ ───────────────────────────────────────▶ │  Servidor (uma máquina)  │
│  (cliente HTTP)    │ ◀─────────────────────────────────────── │  API TLS + bussola.db    │
└────────────────────┘                                          └──────────────────────────┘
┌────────────────────┐                                                     │
│ Segundo terminal   │ ────────────────────────────────────────────────────┘
└────────────────────┘                            backup local + cópia na nuvem
```

- **uma base só**, no servidor — a fonte da verdade é única, como hoje;
- cada terminal é **cliente**: a tela continua igual, o que muda é onde a operação é
  executada;
- o servidor pode ser a máquina do escritório da ONG, uma VM na AWS/Azure
  (`docs/NUVEM.md`) ou um mini-PC na loja;
- se a rede cair, o terminal **avisa e não vende** (melhor do que vender em base
  paralela e descobrir a divergência no fechamento).

## 3. O que já existe (v0.14.0)

| Peça | Estado |
|---|---|
| Rotas de leitura (produtos, estoque, vendas, crediário, turnos, devoluções, relatórios) | ✅ |
| **Rotas de escrita**: venda, abrir/fechar turno, receber título (com encargo), entrada de estoque, devolução, cancelamento | ✅ |
| Token por aplicativo + login/senha por operação (e autorizador quando a regra pede) | ✅ |
| **TLS embutido**: certificado autoassinado gerado pelo programa (`--tls`), sem OpenSSL nem SDK | ✅ |
| Recusa de `--host` de rede sem TLS | ✅ (falha na subida, não vira HTTP aberto) |
| **Identidade de terminal**: `X-Bussola-Terminal` → `vendas.terminal_id`, `turnos.terminal_id` | ✅ (migração 0006) |
| **Log de acesso** JSONL (quando, terminal, IP, rota, status, ms) | ✅ |
| Contexto por thread (conexão SQLite nunca atravessa thread) | ✅ |
| **Teste de concorrência**: dois terminais disputando o último item | ✅ |

### Como subir o servidor hoje

```powershell
# Windows, base em D:\pdv
set BUSSOLA_API_TOKEN=token-longo-e-aleatorio
"D:\Program Files\Python314\python.exe" -m bussola_pdv.cli api `
    --banco D:\pdv\bussola.db --host 0.0.0.0 --porta 8765 --tls --terminal SERVIDOR
```

A saída mostra o endereço `https://…`, o caminho do certificado e a **impressão
digital SHA-256**. O terminal confere essa impressão (por telefone ou olhando a tela
do servidor) antes de confiar no certificado — é o que substitui a autoridade
certificadora numa rede local. O certificado é gerado uma vez em `<dados>\tls` e
reaproveitado nas subidas seguintes.

## 4. O que falta, em ordem

1. **Tela cliente (modo terminal)** — a maior parte do trabalho. O `JanelaPrincipal`
   abre o banco direto; precisa de um "contexto remoto" que implemente os mesmos
   repositórios da tela falando HTTP. Alternativa mais barata: um `bussola terminal`
   que abre **só o PDV** contra o servidor (vender, receber, fechar turno) e deixa o
   resto local.
2. **Fila offline do terminal** — se a rede cair no meio de uma venda, o terminal
   precisa dizer "não vendi" (padrão atual) ou enfileirar com `chave_idempotencia`
   para reenviar. Enfileirar exige decidir o conflito de estoque: recomendação é
   **não** enfileirar venda, apenas bloquear com mensagem clara.
3. **Confiança do certificado no Windows** — instalar o `servidor.crt` no repositório
   "Autoridades de confiança" da máquina do terminal (script `.bat` no instalador),
   para o navegador/curl não reclamarem.
4. **Token por terminal** — hoje um token serve todos; com vários caixas, um token
   por máquina permite revogar um terminal perdido sem derrubar os outros.
5. **Fechamento por terminal** — `turnos.terminal_id` já grava; falta o relatório
   "quanto cada caixa fez", que é o que a loja confere de manhã.
6. **Teste de carga** — 10 terminais simultâneos, medindo latência de venda. O
   SQLite em WAL aguenta bem o volume de um bazar, mas isso precisa de número, não
   de opinião.

## 5. Alternativa descartada por ora: réplica por caixa

Cada caixa com SQLite próprio, sincronizando eventos quando há rede. Funciona com
internet instável, mas custa caro: conflito de estoque, resolução de duplicidade,
relógios diferentes e o mesmo problema de "dois donos do número da venda". Só entra
se a loja tiver **rede instável e vendas simultâneas** — e, nesse caso, a decisão tem
que ser tomada antes, porque muda o modelo de dados.

## 6. Segurança mínima para ligar em rede

- TLS obrigatório — hoje o próprio comando recusa host de rede sem `--tls`;
- um token por terminal, guardado em variável de ambiente da máquina;
- firewall liberando **só** a porta da API, e só para a faixa da loja;
- log de acesso ligado (padrão do comando em modo servidor);
- backup do servidor: local **e** na nuvem (`docs/NUVEM.md`), com restauração testada.

## 7. O que a concorrência faz hoje (e o que ela não faz)

O teste `tests/test_rede_multi_caixa.py` prova o comportamento real:

- **duas vendas do mesmo último item ao mesmo tempo**: uma passa, a outra é recusada
  com mensagem de estoque — não existe estoque negativo silencioso;
- **venda com estoque negativo autorizada** continua sendo possível, mas só por quem
  tem a permissão `PDV_VENDA_ESTOQUE_NEGATIVO` (gerente/admin) e com aviso na
  resposta — é a regra do programa, não um acidente da rede;
- **leituras simultâneas** em threads diferentes não compartilham conexão (cada
  thread abre a sua), então não há corrupção nem bloqueio cruzado.

O que **não** está provado: comportamento com disco lento, rede saturada e 10+
terminais simultâneos (item 6 da lista acima).

## 8. O certificado em si tem teste próprio

`tests/test_certificado.py` (22) não confia no arquivo: **reparseia o DER** e confere

- série **positiva** e diferente a cada geração (série negativa é recusada por
  validador estrito);
- `Name` com RDN em **SET (0x31)** — com SEQUENCE o OpenSSL só diz "PEM lib";
- `subjectAltName` com `localhost`, `127.0.0.1` e o IP local, senão o terminal
  recusa o servidor pelo nome;
- **assinatura RSA conferida matematicamente** (`pow(s, e, n)` com PKCS#1 v1.5),
  não só "o arquivo abre";
- chave privada com permissão `0600` fora do Windows;
- `obter_ou_criar` **reaproveita** o par (regerar trocaria a digital e obrigaria a
  reconfigurar todos os caixas).

O teste achou um defeito real no gerador: `der_inteiro` descartava o byte de sinal e
um inteiro com o bit alto ligado saía **negativo** em DER. Não atingia a série (119
bits, sempre positiva), mas atingiria qualquer campo novo.
