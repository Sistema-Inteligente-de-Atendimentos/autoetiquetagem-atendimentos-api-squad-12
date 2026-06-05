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
- Autenticação de usuários (login) com assinatura de autoria nas análises
- Correção humana da classificação da IA (auditoria), preservando o original da IA
- Medir a acurácia da IA com base na revisão humana
- Filtrar dashboard e lista por período
- Servir dados estruturados para dashboards analíticos
- Exportar os atendimentos em CSV

---

## Stack

- **FastAPI** — API REST
- **SQLAlchemy + PostgreSQL** — persistência
- **Groq API (Llama 3.1 8B)** — classificação via LLM
- **Pandas** — leitura de CSV/Excel e planilhas
- **Pydantic** — validação e serialização
- **Autenticação** — hash de senha (PBKDF2) e token assinado (HMAC), via biblioteca padrão do Python

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
│   ├── classify.py          # Classificação, listagem, detalhe, export, aprovação e correção
│   ├── batch.py             # Processamento em lote (upload CSV/Excel)
│   ├── dashboard.py         # Métricas agregadas e acurácia (com filtro de período)
│   ├── cron.py              # Análise automática a partir do Google Sheets
│   ├── categorias.py        # Gerenciamento de categorias customizadas e planilhas
│   └── auth.py              # Registro, login e dependência de usuário autenticado
└── services/
    ├── llm_service.py       # Integração com a LLM e feedback loop (few-shot dinâmico)
    ├── chat_parser.py       # Divide o texto do chat em mensagens por remetente
    └── auth_service.py      # Hash de senha e geração/validação de token
```

---

## Modelo de Dados

```
channel_chats
 └── channel_chat_protocols (protocolo, número via UUID)
      ├── channel_chat_messages (mensagens, uma por turno)
      └── avaliacoes (classificação da IA + validação/correção humana)

usuarios          (contas de acesso ao sistema)
cron_estado       (contador de linhas processadas por planilha)
cron_config       (planilhas Google Sheets cadastradas)
categorias_custom (categorias adicionais além das 9 fixas)
```

Campos relevantes em `avaliacoes`:
- `json_raw` — classificação atual (corrigida, se houver correção)
- `json_raw_ia` — snapshot da classificação original da IA (preenchido na 1ª correção)
- `analisado_por` — "IA" por padrão; nome do usuário quando corrigida
- `corrigido_em` — data da correção humana
- `aprovado_como_exemplo`, `aprovado_por`, `aprovado_em` — validação humana (feedback loop)

---

## Endpoints

### Autenticação
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/auth/register` | Cria conta e retorna token |
| POST | `/auth/login` | Autentica e retorna token |
| GET | `/auth/me` | Dados do usuário autenticado |

### Atendimentos
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/classify` | Classifica um atendimento individual |
| POST | `/classify/batch` | Processa um lote (upload CSV/Excel, até 50 linhas) |
| GET | `/atendimentos` | Lista resumida dos atendimentos |
| GET | `/atendimentos/export` | Exporta todos os atendimentos em CSV |
| GET | `/atendimentos/{protocolo_id}` | Detalhe completo (chat, mensagens, avaliação, classificação) |
| PUT | `/atendimentos/{protocolo_id}/classificacao` | Corrige a classificação da IA (autenticado) |
| POST | `/atendimentos/{protocolo_id}/aprovar-exemplo` | Marca avaliação como bom exemplo (autenticado) |
| POST | `/atendimentos/{protocolo_id}/remover-exemplo` | Remove a aprovação (autenticado) |

### Dashboard
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/dashboard/stats` | Métricas agregadas (canais, notas, média, exemplos). Aceita `?inicio=&fim=` |
| GET | `/dashboard/acuracia` | Taxa de acerto da IA com base na revisão humana. Aceita `?inicio=&fim=` |

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
| POST | `/config/planilhas/{id}/reset` | Zera o contador de uma planilha específica |
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

### Autenticação e correção humana (auditoria)

Usuários se autenticam (login) e o sistema registra quem corrige cada classificação. A classificação da IA pode ser corrigida por um revisor (`PUT /atendimentos/{id}/classificacao`): os valores são sobrescritos, o original da IA é preservado em `json_raw_ia`, e a assinatura passa de "IA" para o nome do usuário logado, com data. As ações de aprovação/correção exigem autenticação.

### Acurácia da IA

Mede a taxa de acerto da IA com base na revisão humana (`GET /dashboard/acuracia`). O universo são os atendimentos revisados (aprovados como exemplo ou corrigidos): a IA "acertou" quando o caso foi aprovado sem correção, e "errou" quando precisou ser corrigido. A comparação `json_raw_ia` vs `json_raw` indica em quais campos a IA mais erra.

### Filtro de período

Dashboard e lista de atendimentos podem ser filtrados por período (atalhos: hoje, 7 dias, 30 dias, tudo, ou intervalo personalizado). No backend, `/dashboard/stats` e `/dashboard/acuracia` aceitam `inicio` e `fim`.

### Análise automática via Google Sheets (cron)

Planilhas são cadastradas via `POST /config/planilhas`. O backend valida e normaliza a URL (aceita link de edição, compartilhamento ou export). Um cron externo (cron-job.org) dispara `POST /cron/analisar` em um horário fixo. O backend processa todas as planilhas ativas, cada uma com seu próprio contador de linhas, processando apenas as linhas novas a cada disparo.

---

## Variáveis de Ambiente

```env
DATABASE_URL=postgresql://usuario:senha@host:5432/banco
GROQ_API_KEY=sua_chave_groq

# Autenticação (defina um valor aleatório e secreto em produção)
AUTH_SECRET=chave_secreta_para_assinar_tokens

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

### 7. Primeiro acesso

Crie a primeira conta via `POST /auth/register` (ou pela tela de login do frontend, em "Criar conta"). A partir daí, as ações de correção/aprovação ficam atreladas ao usuário logado.

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
