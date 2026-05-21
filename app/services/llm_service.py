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
    - cliente_nome: nome PRÓPRIO do cliente, ou null se não conseguir identificar com certeza.
      IMPORTANTE: "Cliente:" e "Atendente:" são RÓTULOS indicando quem está falando, NÃO são apresentações de nome.
      O texto logo depois de "Cliente:" é a MENSAGEM do cliente, não o nome dele.
      Procure o nome do cliente em:
        * Auto-apresentações: "Meu nome é João", "Aqui é a Ana", "Carlos aqui", "É a Maria"
        * Quando o atendente chama o cliente: "Oi João!", "Sr. Carlos", "Sra. Maria" (extraia apenas "João", "Carlos", "Maria" - SEM os prefixos Sr./Sra.)
        * Assinaturas: "Atenciosamente, Pedro"
      Retorne APENAS o nome próprio em si. Se houver dúvida ou nenhuma menção clara, retorne null.
    - atendente_nome: nome PRÓPRIO do atendente, ou null se não conseguir identificar com certeza.
      IMPORTANTE: o texto logo depois de "Atendente:" é a MENSAGEM do atendente, não o nome dele.
      Procure o nome do atendente em:
        * Auto-apresentações: "Aqui é a Maria do suporte", "Sou o João, do time técnico"
        * Quando o cliente chama o atendente: "Obrigado Pedro!", "Valeu João"
      Retorne APENAS o nome próprio. Se não houver menção clara, retorne null.

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
