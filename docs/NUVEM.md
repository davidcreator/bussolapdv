# Nuvem: AWS e Azure (cópia de segurança e futuro servidor)

> **Status nesta versão:** o **contrato** e a configuração existem e são testados
> (`src/bussola_pdv/infra/nuvem/`), mas **nenhum SDK está instalado**: pedir nuvem
> hoje devolve `NuvemNaoConfigurada` com o motivo, em vez de falhar em silêncio.
> É de propósito — nuvem é decisão de quem paga a conta, não default do programa.

## 1. Para que serve (e para que não serve)

| Serve | Não serve |
|---|---|
| segunda cópia do backup, fora da máquina da loja | operar o caixa (o PDV continua offline) |
| guardar as exportações (Excel/PDF) de meses anteriores | sincronizar dois caixas (isso é `docs/REDE.md`) |
| hospedar o servidor central do multi-caixa, no futuro | autenticar operador (isso é local, com senha) |

Regra que não muda: **o caixa não depende da internet**. Se a nuvem cair, o bazar
vende, fecha o turno e faz backup local; a cópia na nuvem acontece depois.

## 2. Contrato (o que qualquer provedor precisa cumprir)

```python
class ArmazenamentoNuvem(Protocol):
    def enviar(self, caminho: Path, *, nome: str | None = None) -> str: ...
    def baixar(self, nome: str, destino: Path) -> Path: ...
    def listar(self) -> list[str]: ...
    def remover(self, nome: str) -> None: ...
```

Quem chama é `enviar_backup(armazenamento, caminho)` — o serviço de backup
(`ServicoBackup`) já produz o arquivo com **manifesto e `sha256`**; a nuvem só
transporta. Implementações: `ArmazenamentoS3`, `ArmazenamentoAzureBlob` (esqueletos
que recusam com mensagem) e `ArmazenamentoMemoria` (dublê usado nos testes).

## 3. Configuração

```python
ConfiguracaoNuvem(
    provedor="S3",                 # "S3" | "AZURE_BLOB"
    recipiente="bussolapdv-bazar", # bucket (S3) ou container (Azure)
    regiao="sa-east-1",            # ou "brazilsouth" no Azure
    prefixo="bussolapdv/",
    conta="",                      # Azure: nome da conta de armazenamento
    variavel_chave="BUSSOLA_NUVEM_CHAVE",
    endpoint="",                   # S3-compatível (MinIO, Wasabi, R2)
    criptografia="AES256",         # SSE-S3
)
```

**Segredo nunca no banco nem no código**: o nome da variável de ambiente é o que
fica na configuração; a chave fica na máquina (ou no cofre do sistema).

## 4. AWS — passo a passo

1. Criar o balde na região mais próxima (`sa-east-1`), com **Block Public Access**
   ligado, versionamento e criptografia SSE-S3 por padrão.
2. Criar um usuário IAM **só** para o backup, sem console, com esta política mínima:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"],
    "Resource": [
      "arn:aws:s3:::bussolapdv-bazar",
      "arn:aws:s3:::bussolapdv-bazar/bussolapdv/*"
    ]
  }]
}
```

3. Gerar a **chave de acesso** do usuário e salvar na máquina:
   `setx BUSSOLA_NUVEM_CHAVE "…"` (Windows) — sem eco no histórico do shell.
4. Regra de ciclo de vida: transição para *Glacier Instant Retrieval* em 30 dias,
   expiração em 365; manter as **14 cópias locais** como hoje.
5. Implementar `ArmazenamentoS3` com `boto3` (4 métodos, ~40 linhas) e um teste de
   integração marcado como opcional (`@pytest.mark. integracao`).

## 5. Azure — passo a passo

1. Conta de armazenamento em `brazilsouth`, com **hierarquia de namespace** desligada
   (blob simples), acesso público desabilitado e criptografia gerenciada pela
   plataforma.
2. Criar o container `bussolapdv-bazar` com acesso privado.
3. Criar um **SAS token** ou uma *managed identity* com papel
   `Storage Blob Data Contributor` restrito ao container.
4. Guardar a string de conexão/SAS na variável de ambiente indicada em
   `variavel_chave`.
5. Implementar `ArmazenamentoAzureBlob` com `azure-storage-blob` (mesmos 4 métodos).

## 6. O que a loja precisa decidir

| Decisão | Padrão sugerido |
|---|---|
| Provedor | o que a ONG já usa (doação de crédito em nuvem é comum) |
| Região | São Paulo (`sa-east-1` / `brazilsouth`) — latência e LGPD |
| Retenção | 30 dias na nuvem, 14 cópias locais, 5 anos para XML fiscal (quando houver) |
| Custo | alguns reais por mês para o volume do bazar |
| LGPD | dado pessoal em nuvem exige base legal, prazo de guarda e registro (pendência P6) |
| Quem tem a chave | uma pessoa nomeada; a chave não é compartilhada por WhatsApp |

## 7. Por que não integrar agora

Instalar SDK, criar conta, testar credencial e homologar custódia de dado pessoal é
trabalho de integração — e nenhum dele muda a vida do bazar enquanto o backup local
funciona. O que a base desta versão garante é que **quando a decisão vier, não se
reescreve o backup**: troca-se a implementação do contrato.
