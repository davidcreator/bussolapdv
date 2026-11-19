# Cópia de segurança na nuvem (AWS S3 e Azure Blob)

> **Status na v0.14.0:** os **dois clientes funcionam de verdade**, em biblioteca
> padrão (`infra/nuvem/s3.py` e `infra/nuvem/azure.py`), com as assinaturas AWS
> Signature V4 e Azure Shared Key conferidas contra os exemplos publicados dos
> fornecedores. O que falta é só a **conta e a chave** — decisão de quem paga.
>
> Sem SDK: `boto3` e `azure-storage-blob` não entram na instalação do Windows.

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
transporta. Implementações:

| Classe | O que faz |
|---|---|
| `ArmazenamentoS3` | `PUT`/`GET`/`DELETE`/listagem no S3 (ou MinIO/Wasabi/R2 por `endpoint`) |
| `ArmazenamentoAzureBlob` | o mesmo no Azure Blob, com `BlockBlob` |
| `ArmazenamentoMemoria` | dublê de teste, sem rede |

## 3. Configuração e credencial

```python
ConfiguracaoNuvem(
    provedor="S3",                 # "S3" | "AZURE_BLOB"
    recipiente="bussolapdv-bazar", # bucket (S3) ou container (Azure)
    regiao="sa-east-1",            # ou "brazilsouth" no Azure
    prefixo="bussolapdv/",
    conta="",                      # Azure: nome da conta de armazenamento
    variavel_chave="",             # opcional: nome de outra variável
    variavel_acesso="",            # opcional: idem, para a chave de acesso
    endpoint="",                   # S3-compatível (MinIO, Wasabi, R2)
    criptografia="AES256",         # SSE-S3
)
```

Variáveis de ambiente lidas (padrão):

| Variável | Para quê |
|---|---|
| `BUSSOLA_AWS_ACCESS_KEY_ID` | id da chave do usuário IAM |
| `BUSSOLA_AWS_SECRET_ACCESS_KEY` | segredo do usuário IAM |
| `BUSSOLA_AWS_SESSION_TOKEN` | opcional, credencial temporária |
| `BUSSOLA_AWS_REGIAO` | padrão `sa-east-1` |
| `BUSSOLA_AZURE_CONTA` | nome da conta de armazenamento |
| `BUSSOLA_AZURE_CHAVE` | chave da conta, **em base64** |
| `BUSSOLA_NUVEM_RECIPIENTE` | balde/contêiner, quando não vier na linha de comando |

**Segredo nunca no banco nem no código.** Sem as variáveis, o cliente **não nasce** e
a mensagem diz exatamente qual variável falta — em vez de tentar falar com a nuvem e
falhar com um erro de rede genérico.

### Como mandar a cópia (linha de comando)

```bash
# S3
python -m bussola_pdv.cli backup --banco dados/bussola.db \
    --nuvem aws --nuvem-recipiente bussolapdv-bazar --nuvem-regiao sa-east-1

# Azure
python -m bussola_pdv.cli backup --banco dados/bussola.db \
    --nuvem azure --nuvem-recipiente backups
```

Saída: a cópia local é criada e **verificada** primeiro; depois o `.db` e o `.json` do
manifesto sobem. Se a nuvem falhar, o comando diz o motivo, avisa que a cópia local
está intacta e sai com código 2 — rotina agendada enxerga a falha.

### Por que a assinatura é nossa

| Alternativa | Por que não |
|---|---|
| SDK (`boto3`, `azure-storage-blob`) | dependência nova na instalação do Windows, versão que quebra, download no cliente |
| `curl` externo | não existe no Windows por padrão e não assina SigV4 |
| SigV4/Shared Key em `hmac` + `hashlib` | ~150 linhas, conferidas contra os exemplos publicados dos dois fornecedores |

Os testes (`tests/test_nuvem_clientes.py`) provam duas coisas separadas: a
canonicalização está **idêntica à documentação** (o `Authorization` do exemplo da AWS
e o `StringToSign` do exemplo da Microsoft, comparados byte a byte) e o cliente faz
ida e volta completa contra um servidor falso local que exige assinatura.

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

1. Conta de armazenamento em `brazilsouth`, com **namespace hierárquico desligado**
   (blob simples), acesso público desabilitado e criptografia gerenciada pela
   plataforma.
2. Criar o contêiner `bussolapdv-bazar` com acesso privado.
3. Em **Chaves de acesso**, copiar o nome da conta e uma das chaves (a chave já vem
   em base64 — é exatamente o que `BUSSOLA_AZURE_CHAVE` espera).
4. Exportar na máquina do servidor:

```powershell
setx BUSSOLA_AZURE_CONTA "bussolapdvbazar"
setx BUSSOLA_AZURE_CHAVE "cole-a-chave-base64-aqui"
```

5. Testar: `python -m bussola_pdv.cli backup --banco dados\bussola.db --nuvem azure --nuvem-recipiente bussolapdv-bazar`

O cliente usa **Shared Key** (chave da conta). Managed identity/Entra ID é o caminho
recomendado pela Microsoft para quem roda dentro do Azure — exige SDK, então fica
para quando o servidor central estiver numa VM da Azure.

## 6. O que a loja precisa decidir

| Decisão | Padrão sugerido |
|---|---|
| Provedor | o que a ONG já usa (doação de crédito em nuvem é comum) |
| Região | São Paulo (`sa-east-1` / `brazilsouth`) — latência e LGPD |
| Retenção | 30 dias na nuvem, 14 cópias locais, 5 anos para XML fiscal (quando houver) |
| Custo | alguns reais por mês para o volume do bazar |
| LGPD | dado pessoal em nuvem exige base legal, prazo de guarda e registro (pendência P6) |
| Quem tem a chave | uma pessoa nomeada; a chave não é compartilhada por WhatsApp |

## 7. O que foi decidido (e o que continua aberto)

**Decidido (ADR-034):** clientes em biblioteca padrão, credencial por variável de
ambiente, `bussola backup --nuvem aws|azure` mandando cópia + manifesto, e falha de
nuvem **nunca** invalidando a cópia local.

**Aberto:** contratar a conta (custo e quem paga), política de retenção por escrito,
registro de tratamento de dado pessoal (LGPD, pendência P6) e a rotina agendada —
hoje o comando é manual; agendar no Windows é uma tarefa do instalador.

## 8. Limites conhecidos

| Limite | Consequência |
|---|---|
| Sem multipart upload | arquivos acima de ~5 GB não sobem (backup de bazar fica em MB) |
| Sem retry automático | rede caiu? o comando falha e diz; a cópia local continua |
| Sem listagem paginada | mais de 1000 objetos: a listagem mostra a primeira página |
| Sem download em massa | restaurar é `baixar(nome, destino)`, um por vez |
