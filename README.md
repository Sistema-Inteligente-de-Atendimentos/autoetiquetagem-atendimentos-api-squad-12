# Sistema de Autoetiquetagem Inteligente de Atendimentos

API backend desenvolvida com FastAPI para processamento e classificação automática de atendimentos utilizando LLM (Groq / Llama 3.1).

---

## Visão Geral

Este projeto implementa um motor de autoetiquetagem capaz de:

- Classificar atendimentos automaticamente (categoria, intenção, sentimento, criticidade)
- Avaliar a qualidade do atendimento (empatia, clareza, objetividade, resolutividade)
- Calcular um score final ponderado a partir dos critérios de qualidade
- Extrair automaticamente o nome do cliente e do atendente a partir do texto
- Separar o histórico do chat em mensagens individuais por remetente
- Processar atendimentos em lote (CSV/Excel)
- Processar atendimentos automaticamente a partir de uma planilha Google Sheets (cron)
- Aprender continuamente com exemplos aprovados por humanos (feedback loop)
- Servir dados estruturados para dashboards analíticos
- Exportar os atendimentos em CSV

---

## Stack

- **FastAPI** — API REST
- **SQLAlchemy + PostgreSQL** — persistência
- **Groq API (Llama 3.1 8B)** — classificação via LLM
- **Pandas** — leitura de CSV/Excel e planilhas
- **Pydantic** — validação e serialização

---

## Estrutura do Projeto

```
app/
├── main.py                  # Inicializa o FastAPI, registra rotas e migrations
├── config.py                # Engine, sessão e Base do SQLAlchemy
├── models.py                # Modelos ORM (Chat, Protocolo, Mensagem, Avaliação, CronEstado)
├── schemas.py               # Schemas Pydantic de entrada/saída
├── core/
│   └── taxonomy.py          # Taxonomia fechada e cálculo do score ponderado
├── routes/
│   ├── classify.py          # Classificação individual, listagem, detalhe, export, aprovação
│   ├── batch.py             # Processamento em lote (upload CSV/Excel)
│   ├── dashboard.py         # Métricas agregadas
│   └── cron.py              # Análise automática a partir do Google Sheets
└── services/
    ├── llm_service.py       # Integração com a LLM e feedback loop (few-shot dinâmico)
    └── chat_parser.py       # Divide o texto do chat em mensagens por remetente
```

---

## Modelo de Dados

Hierarquia das tabelas:

```
ChannelChat (atendimento)
 └── ChannelChatProtocol (protocolo, número via UUID)
      ├── ChannelChatMessage (mensagens, uma por turno do chat)
      └── Avaliacao (classificação da IA + validação humana)

CronEstado (controle de linhas já processadas por planilha)
```

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/classify` | Classifica um atendimento individual |
| POST | `/classify/batch` | Processa um lote (upload CSV/Excel, até 50 linhas) |
| GET | `/atendimentos` | Lista resumida dos atendimentos |
| GET | `/atendimentos/export` | Exporta todos os atendimentos em CSV |
| GET | `/atendimentos/{protocolo_id}` | Detalhe completo (chat, mensagens, avaliação) |
| POST | `/atendimentos/{protocolo_id}/aprovar-exemplo` | Marca a avaliação como bom exemplo |
| POST | `/atendimentos/{protocolo_id}/remover-exemplo` | Remove a aprovação |
| GET | `/dashboard/stats` | Métricas agregadas (volume por canal, distribuição de notas, média, exemplos) |
| POST | `/cron/analisar` | Dispara a análise da planilha (protegido por token) |
| GET | `/cron/status` | Progresso do processamento por planilha |

---

## Funcionalidades Principais

### Taxonomia fechada e score ponderado

As categorias, sentimentos e criticidades permitidos são definidos em `core/taxonomy.py`.
A saída da IA é normalizada contra essa lista (valores fora da taxonomia caem em "Outros").
O `score_final` é recalculado pela média ponderada dos 4 critérios de qualidade (pesos configuráveis).

### Extração de nomes e separação de mensagens

A IA identifica cliente e atendente a partir do texto quando não informados.
O `chat_parser.py` divide o texto em mensagens individuais (Cliente / Atendente),
renderizadas no front como uma conversa em balões.

### Feedback loop (few-shot dinâmico)

Atendimentos aprovados como "bom exemplo" são injetados no prompt das próximas
classificações, melhorando a consistência sem retreinar o modelo.

### Análise automática via Google Sheets (cron)

Um cron externo (ex: cron-job.org) dispara `POST /cron/analisar` em um horário fixo.
O backend lê uma planilha pública do Google Sheets, processa apenas as linhas novas
(controle por contagem no banco) e salva os resultados.

---

## Variáveis de Ambiente

```env
DATABASE_URL=postgresql://usuario:senha@host:5432/banco
GROQ_API_KEY=sua_chave_groq

# Cron (análise via Google Sheets)
CRON_TOKEN=token_secreto_para_proteger_o_endpoint
GOOGLE_SHEET_ID=id_da_planilha
GOOGLE_SHEET_GID=0
# Alternativamente, em vez de GOOGLE_SHEET_ID:
# GOOGLE_SHEET_CSV_URL=url_completa_de_export_csv
```

---

## Como rodar o projeto

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd <nome-do-projeto>
```

### 2. Criar e ativar o ambiente virtual

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar o `.env`

Crie um arquivo `.env` na raiz com as variáveis listadas acima.

### 5. Rodar a aplicação

```bash
uvicorn app.main:app --reload
```

As tabelas são criadas automaticamente no startup (`create_all` + migrations idempotentes).

### 6. Acessar a documentação interativa

```
http://127.0.0.1:8000/docs
```

---

## Configuração do Cron (produção)

1. Crie uma planilha no Google Sheets com a coluna `texto` (e opcionalmente `canal`, `cliente`, `atendente`).
2. Compartilhe como "Qualquer pessoa com o link" (Leitor).
3. Configure `GOOGLE_SHEET_ID`, `GOOGLE_SHEET_GID` e `CRON_TOKEN` no ambiente.
4. Em um agendador externo (cron-job.org), crie um job:
   - URL: `https://<sua-api>/cron/analisar`
   - Método: `POST`
   - Header: `Authorization: Bearer <CRON_TOKEN>`
   - Frequência: diária, no horário desejado.

O endpoint processa em background, evitando timeout no plano free do Render.
