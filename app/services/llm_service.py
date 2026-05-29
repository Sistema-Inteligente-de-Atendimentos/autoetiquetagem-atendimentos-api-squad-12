import json
import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.taxonomy import (
    CATEGORIAS,
    CRITICIDADES,
    SENTIMENTOS,
    validar_classificacao,
)
from app.models import Avaliacao, ChannelChat, ChannelChatProtocol

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


def buscar_exemplos_aprovados(
    db: Session,
    limite: int = 3,
    canal: Optional[str] = None,
) -> List[Avaliacao]:
    query = (
        db.query(Avaliacao)
        .options(joinedload(Avaliacao.protocolo).joinedload(ChannelChatProtocol.mensagens))
        .filter(Avaliacao.aprovado_como_exemplo.is_(True))
        .filter(Avaliacao.json_raw.isnot(None))
    )

    if canal:
        query = query.join(ChannelChatProtocol).join(ChannelChat).filter(
            ChannelChat.canal == canal
        )

    exemplos = query.order_by(func.random()).limit(limite).all()
    return exemplos


def _formatar_exemplos(exemplos: List[Avaliacao]) -> str:
    if not exemplos:
        return ""

    blocos = []
    for ex in exemplos:
        try:
            classificacao = json.loads(ex.json_raw or "{}")
        except Exception:
            continue

        mensagens = ex.protocolo.mensagens if ex.protocolo else []
        trecho = mensagens[0].conteudo[:250] if mensagens else "(sem texto)"

        qualidade = classificacao.get("qualidade", {}) or {}

        bloco = f"""---
Texto: "{trecho}..."
Classificação correta:
  categoria: "{classificacao.get('categoria', 'N/A')}"
  intencao: "{classificacao.get('intencao', 'N/A')}"
  sentimento: "{classificacao.get('sentimento', 'N/A')}"
  criticidade: "{classificacao.get('criticidade', 'N/A')}"
  score_final: {qualidade.get('score_final', 'N/A')}"""
        blocos.append(bloco)

    if not blocos:
        return ""

    return (
        "\n\nEXEMPLOS DE CLASSIFICAÇÕES JÁ VALIDADAS POR ESPECIALISTAS HUMANOS "
        "(siga o mesmo padrão e critérios):\n"
        + "\n".join(blocos)
        + "\n---\n"
    )


def classify_text(text: str, exemplos: Optional[List[Avaliacao]] = None):
    exemplos_texto = _formatar_exemplos(exemplos or [])

    categorias_str = ", ".join(CATEGORIAS)
    sentimentos_str = ", ".join(SENTIMENTOS)
    criticidades_str = ", ".join(CRITICIDADES)

    prompt = f"""
    Você é um sistema de classificação de atendimentos.
    {exemplos_texto}
    Analise o texto abaixo e retorne um JSON válido com:

    - categoria: escolha EXATAMENTE uma destas opções (não invente outras): {categorias_str}. Se nenhuma encaixar, use "Outros".
    - intencao
    - sentimento: escolha uma destas: {sentimentos_str}
    - criticidade: escolha uma destas: {criticidades_str}
    - sla_urgencia
    - qualidade:
        - empatia (0-10)
        - clareza (0-10)
        - objetividade (0-10)
        - resolutividade (0-10)
        - score_final (0-10)
    - resumo (máx 3 linhas)
    - topicos (lista)
    - cliente_nome: nome do cliente extraído do texto (apenas o primeiro nome ou nome completo), ou null se realmente não houver nenhuma menção.
    - atendente_nome: nome do atendente extraído do texto, ou null se realmente não houver nenhuma menção.

    REGRAS PARA EXTRAIR NOMES:

    1. "Cliente:" e "Atendente:" são RÓTULOS de fala, NUNCA são o nome. Ignore-os.

    2. Os nomes podem aparecer em vários padrões. Sempre que houver UMA menção clara, extraia.

    Exemplos de extração correta:

    Texto: "Cliente: Meu nome é Marcelo. Atendente: Oi Marcelo, aqui é a Júlia."
    cliente_nome: "Marcelo", atendente_nome: "Júlia"

    Texto: "Cliente: O sistema caiu! Atendente: Sr. Roberto, vou verificar. Aqui é a Ana."
    cliente_nome: "Roberto", atendente_nome: "Ana"
    (Sr. Roberto = o atendente está se dirigindo ao cliente Roberto. Extraia "Roberto" sem o "Sr.")

    Texto: "Cliente: Bom dia, aqui é a Patrícia. Atendente: Oi Patrícia, sou o Rafael."
    cliente_nome: "Patrícia", atendente_nome: "Rafael"

    Texto: "Cliente: Quero cancelar. Atendente: Posso saber o motivo? Cliente: Carlos aqui, achei caro."
    cliente_nome: "Carlos", atendente_nome: null

    Texto: "Cliente: Obrigado pelo atendimento rápido João! Atendente: De nada!"
    cliente_nome: null, atendente_nome: "João"

    Texto: "Cliente: Quanto custa o plano premium? Atendente: R$ 79,90 por mês."
    cliente_nome: null, atendente_nome: null
    (nenhum nome aparece no texto)

    Retorne APENAS o nome próprio (sem "Sr.", "Sra.", "Dr." e sem sobrenomes que não foram mencionados).

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
        # Normaliza contra a taxonomia fechada e recalcula o score ponderado
        parsed = validar_classificacao(parsed)
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
