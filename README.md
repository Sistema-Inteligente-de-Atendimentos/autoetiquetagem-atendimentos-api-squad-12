# Sistema de Autoetiquetagem Inteligente de Atendimentos

API backend desenvolvida com FastAPI para processamento e classificação automática de atendimentos utilizando LLM.

---

## Visão Geral

Este projeto implementa um motor de autoetiquetagem capaz de:

- Classificar atendimentos automaticamente
- Avaliar qualidade do atendimento
- Gerar resumos e tópicos
- Permitir validação humana
- Servir dados para dashboards analíticos

---

## Arquitetura

A aplicação segue uma arquitetura em camadas simples e escalável:


---

## 📁 Estrutura do Projeto

---

## 🔧 Responsabilidade de cada camada

### `main.py`
- Inicializa a aplicação FastAPI
- Registra as rotas

---

### `routes/`
- Define os endpoints da API
- Recebe requisições
- Valida dados de entrada
- Retorna respostas

---

### `services/`
- Contém a lógica de negócio
- Integra com o modelo de IA (LLM)
- Processa e estrutura os dados

---

## 🚀 Como rodar o projeto

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd <nome-do-projeto>
```
### 2. Criar ambiente virtual

```bash
python -m venv venv
```

### 3. Ativar ambiente virtual
Windows:
```bash
venv\Scripts\activate
```


Linux/Mac:
```bash
source venv/bin/activate
```

### 4. Instalar dependências
```bash
pip install fastapi uvicorn python-dotenv openai
```
### 5. Rodar a aplicação
```bash
uvicorn app.main:app --reload
```
### 6. Acessar a documentação interativa
```bash
http://127.0.0.1:8000/docs
```
