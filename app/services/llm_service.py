import os
import re
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


def classify_text(text: str):
    prompt = f"""
    Você é um sistema de classificação de atendimentos.

    Analise o texto abaixo e retorne um JSON válido com:

    - categoria
    - intencao
    - sentimento (Positivo, Neutro, Negativo)
    - criticidade (Baixa, Média, Alta)
    - sla_urgencia
    - qualidade:
        - empatia (0-10)
        - clareza (0-10)
        - objetividade (0-10)
        - resolutividade (0-10)
        - score_final (0-10)
    - resumo (máx 3 linhas)
    - topicos (lista)
    - cliente_nome: nome do cliente identificado no texto, ou null se não conseguir identificar.
      Procure por padrões como "Cliente: Nome", assinaturas, apresentações ("Meu nome é...", "Aqui é o..."),
      ou qualquer menção explícita ao nome do cliente. Retorne APENAS o nome próprio (sem prefixos como "Sr." ou "Sra.").
    - atendente_nome: nome do atendente identificado no texto, ou null se não conseguir identificar.
      Procure por padrões como "Atendente: Nome", apresentações ("Aqui é a Maria do suporte..."),
      ou qualquer menção explícita ao nome do atendente. Retorne APENAS o nome próprio.

    TEXTO:
    {text}

    Responda APENAS com JSON válido.
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Responda apenas em JSON válido."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    content = response.choices[0].message.content

    clean_content = re.sub(r"```json|```", "", content).strip()

    try:
        parsed = json.loads(clean_content)

        return {
            "data": parsed,
            "usage": response.usage
        }
    except Exception:
        return {
            "error": "Invalid JSON",
            "raw_response": content,
            "usage": response.usage
        }
