from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.config import Base


class ChannelChat(Base):
    __tablename__ = "channel_chats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_nome = Column("ClienteNome", String(150), nullable=True)
    atendente_nome = Column("AtendenteNome", String(150), nullable=True)
    canal = Column("Canal", String(50), nullable=True)
    iniciado_em = Column("IniciadoEm", DateTime(timezone=True), server_default=func.now())
    encerrado_em = Column("EncerradoEm", DateTime(timezone=True), nullable=True)

    protocolos = relationship(
        "ChannelChatProtocol",
        back_populates="chat",
        cascade="all, delete-orphan",
    )
    mensagens = relationship(
        "ChannelChatMessage",
        back_populates="chat",
        cascade="all, delete-orphan",
    )


class ChannelChatProtocol(Base):
    __tablename__ = "channel_chat_protocols"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_chat_id = Column(
        "ChannelChatId",
        Integer,
        ForeignKey("channel_chats.id"),
        nullable=False,
        index=True,
    )
    numero = Column("Numero", String(100), nullable=False, unique=True, index=True)
    aberto_em = Column("AbertoEm", DateTime(timezone=True), server_default=func.now())
    fechado_em = Column("FechadoEm", DateTime(timezone=True), nullable=True)

    chat = relationship("ChannelChat", back_populates="protocolos")
    mensagens = relationship(
        "ChannelChatMessage",
        back_populates="protocolo",
        cascade="all, delete-orphan",
        order_by="ChannelChatMessage.id",
    )
    avaliacoes = relationship(
        "Avaliacao",
        back_populates="protocolo",
        cascade="all, delete-orphan",
    )


class ChannelChatMessage(Base):
    __tablename__ = "channel_chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_chat_id = Column(
        "ChannelChatId",
        Integer,
        ForeignKey("channel_chats.id"),
        nullable=False,
        index=True,
    )
    protocolo_id = Column(
        "ProtocoloId",
        Integer,
        ForeignKey("channel_chat_protocols.id"),
        nullable=False,
        index=True,
    )
    remetente = Column("Remetente", String(100), nullable=True)
    conteudo = Column("Conteudo", Text, nullable=False)
    enviada_em = Column("EnviadaEm", DateTime(timezone=True), server_default=func.now())

    chat = relationship("ChannelChat", back_populates="mensagens")
    protocolo = relationship("ChannelChatProtocol", back_populates="mensagens")


class Avaliacao(Base):
    __tablename__ = "avaliacoes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    protocolo_id = Column(
        "ProtocoloId",
        Integer,
        ForeignKey("channel_chat_protocols.id"),
        nullable=False,
        index=True,
    )
    nota = Column("Nota", Integer, nullable=True)
    comentario = Column("Comentario", Text, nullable=True)
    avaliado_em = Column("AvaliadoEm", DateTime(timezone=True), server_default=func.now())

    json_raw = Column("JsonRaw", Text, nullable=True)
    aprovado_como_exemplo = Column("AprovadoComoExemplo", Boolean, default=False, nullable=False, index=True)
    aprovado_por = Column("AprovadoPor", String(150), nullable=True)
    aprovado_em = Column("AprovadoEm", DateTime(timezone=True), nullable=True)
    observacao_aprovacao = Column("ObservacaoAprovacao", Text, nullable=True)

    protocolo = relationship("ChannelChatProtocol", back_populates="avaliacoes")
