from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class _ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MensagemOut(_ORMModel):
    id: int
    remetente: Optional[str] = None
    conteudo: str
    enviada_em: Optional[datetime] = None


class AvaliacaoOut(_ORMModel):
    id: int
    nota: Optional[int] = None
    comentario: Optional[str] = None
    avaliado_em: Optional[datetime] = None
    aprovado_como_exemplo: bool = False
    aprovado_por: Optional[str] = None
    aprovado_em: Optional[datetime] = None
    observacao_aprovacao: Optional[str] = None


class ChatOut(_ORMModel):
    id: int
    cliente_nome: Optional[str] = None
    atendente_nome: Optional[str] = None
    canal: Optional[str] = None
    iniciado_em: Optional[datetime] = None
    encerrado_em: Optional[datetime] = None


class ProtocoloDetalheOut(_ORMModel):
    id: int
    numero: str
    aberto_em: Optional[datetime] = None
    fechado_em: Optional[datetime] = None
    chat: ChatOut
    mensagens: List[MensagemOut] = []
    avaliacao: Optional[AvaliacaoOut] = None


class ClassifyResponse(BaseModel):
    status: str
    chat_id: int
    protocolo_id: int
    protocolo_numero: str
    mensagem_id: int
    avaliacao_id: int
    data: dict


class CanalStat(BaseModel):
    canal: str
    total: int


class NotaStat(BaseModel):
    nota: int
    total: int


class DashboardStats(BaseModel):
    total_atendimentos: int
    media_qualidade: float
    volume_por_canal: List[CanalStat]
    distribuicao_notas: List[NotaStat]
    total_exemplos_aprovados: int = 0


class AprovarExemploRequest(BaseModel):
    revisor: str
    observacao: Optional[str] = None
