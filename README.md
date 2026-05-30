# Sistema de Autoetiquetagem Inteligente de Atendimentos

API backend desenvolvida com FastAPI para processamento e classificação automática de atendimentos utilizando LLM (Groq / Llama 3.1).

---

## Visão Geral

- Classificar atendimentos automaticamente (categoria, intenção, sentimento, criticidade)
- Avaliar a qualidade do atendimento (empatia, clareza, objetividade, resolutividade)
- Calcular um score final ponderado a partir dos critérios de qualidade
- Extrair automaticamente o nome do cliente e do atendente a partir do texto
- Separar o histórico do chat em mensagens individuais por remetente
- Processar atendimentos em lote (CSV/Excel)
- Processar atendimentos automaticamente a partir de planilhas Google Sheets (cron)
- Gerenciar múltiplas planilhas de origem via interface
- Aprender continuamente com exemplos aprovados por humanos (feedback loop)
- Gerenciar categorias customizadas via interface
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
├── models.py                # Modelos ORM
├── schemas.py               # Schemas Pydantic de entrada/saída
├── core/
│   └── taxonomy.py          # Taxonomia fechada, categorias fixas e cálculo do score ponderado
├── routes/
│   ├── classify.py          # Classificação individual, listagem, detalhe, export, aprovação
│   ├── batch.py             # Processamento em lote (upload CSV/Excel)
│   ├── dashboard.py         # Métricas agregadas
│   ├── cron.py              # Análise automática a partir do Google Sheets
│   └── categorias.py        # Gerenciamento de categorias customizadas e planilhas
└── services/
    ├── llm_service.py       # Integração com a LLM e feedback loop (few-shot dinâmico)
    └── chat_parser.py       # Divide o texto do chat em mensagens por remetente
```

---

## Modelo de Dados

```
channel_chats
 └── channel_chat_protocols (protocolo, número via UUID)
      ├── channel_chat_messages (mensagens, uma por turno)
      └── avaliacoes (classificação da IA + validação humana)

cron_estado       (contador de linhas processadas por planilha)
cron_config       (planilhas Google Sheets cadastradas)
categorias_custom (categorias adicionais além das 9 fixas)
```

---

## Endpoints

### Atendimentos
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/classify` | Classifica um atendimento individual |
| POST | `/classify/batch` | Processa um lote (upload CSV/Excel, até 50 linhas) |
| GET | `/atendimentos` | Lista resumida dos atendimentos |
| GET | `/atendimentos/export` | Exporta todos os atendimentos em CSV |
| GET | `/atendimentos/{protocolo_id}` | Detalhe completo (chat, mensagens, avaliação) |
| POST | `/atendimentos/{protocolo_id}/aprovar-exemplo` | Marca avaliação como bom exemplo |
| POST | `/atendimentos/{protocolo_id}/remover-exemplo` | Remove a aprovação |

### Dashboard
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/dashboard/stats` | Métricas agregadas (canais, notas, média, exemplos aprovados) |

### Cron
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/cron/analisar` | Dispara análise das planilhas ativas (protegido por token) |
| GET | `/cron/status` | Progresso por planilha |
| POST | `/cron/reset` | Zera o contador (reprocessa tudo no próximo disparo) |

### Configuração
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/config/planilhas` | Lista planilhas cadastradas com progresso |
| POST | `/config/planilhas` | Adiciona planilha (valida URL antes de salvar) |
| PATCH | `/config/planilhas/{id}/ativar` | Ativa uma planilha |
| PATCH | `/config/planilhas/{id}/desativar` | Desativa sem remover |
| DELETE | `/config/planilhas/{id}` | Remove planilha e seu histórico |
| GET | `/config/categorias` | Lista categorias fixas e customizadas |
| POST | `/config/categorias` | Adiciona categoria customizada |
| DELETE | `/config/categorias/{id}` | Remove categoria customizada |

---

## Funcionalidades Principais

### Taxonomia fechada e score ponderado

As 9 categorias base (`Financeiro`, `Técnico`, `Comercial`, `Logística`, `Reclamação`, `Elogio`, `Cancelamento`, `Dúvida`, `Outros`) são fixas e definidas em `core/taxonomy.py`. Novas categorias podem ser adicionadas via `POST /config/categorias` e são automaticamente incluídas no prompt da IA. O `score_final` é calculado em código pela média ponderada dos 4 critérios de qualidade, não confiando no número retornado pela IA.

### Extração de nomes e separação de mensagens

A IA identifica cliente e atendente a partir do texto via few-shot prompting quando não informados. O `chat_parser.py` divide o texto em mensagens individuais por remetente, renderizadas no front como uma conversa em balões.

### Feedback loop (few-shot dinâmico)

Atendimentos aprovados como "bom exemplo" são injetados no prompt das próximas classificações, melhorando a consistência sem retreinar o modelo. A busca prioriza exemplos do mesmo canal.

### Análise automática via Google Sheets (cron)

Planilhas são cadastradas via `POST /config/planilhas`. O backend valida se o CSV está acessível antes de salvar. Um cron externo (cron-job.org) dispara `POST /cron/analisar` em um horário fixo. O backend processa todas as planilhas ativas, cada uma com seu próprio contador de linhas. Novas linhas adicionadas à planilha são processadas automaticamente no próximo disparo.

---

## Variáveis de Ambiente

```env
DATABASE_URL=postgresql://usuario:senha@host:5432/banco
GROQ_API_KEY=sua_chave_groq

# Obrigatório para o cron
CRON_TOKEN=token_secreto_para_proteger_o_endpoint

# Opcional — fallback legado (planilhas agora são gerenciadas via /config/planilhas)
GOOGLE_SHEET_ID=id_da_planilha
GOOGLE_SHEET_GID=0
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
3. Na interface do sistema (`/configuracoes`), adicione a URL da planilha em **Planilhas Google Sheets**.
4. Configure `CRON_TOKEN` no ambiente (Render → Environment).
5. Em um agendador externo (cron-job.org), crie um job:
   - URL: `https://<sua-api>/cron/analisar`
   - Método: `POST`
   - Header: `Authorization: Bearer <CRON_TOKEN>`
   - Frequência: diária, no horário desejado.

O endpoint processa em background, evitando timeout no plano free do Render. Múltiplas planilhas são processadas em sequência a cada disparo.
