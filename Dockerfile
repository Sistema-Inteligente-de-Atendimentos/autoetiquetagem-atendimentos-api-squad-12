# Usamos uma versão leve do Python
FROM python:3.11-slim

# Define a pasta de trabalho dentro do container
WORKDIR /app

# Evita que o Python gere arquivos .pyc e permite logs em tempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instalamos as dependências do sistema necessárias (se houver)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copiamos o arquivo de dependências primeiro (otimiza o cache do Docker)
COPY requirements.txt .

# Instalamos as bibliotecas do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos o restante dos arquivos do projeto para dentro do container
COPY . .

# O Railway define a porta automaticamente via variável de ambiente PORT
# Usamos o host 0.0.0.0 para que a API seja acessível externamente
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]