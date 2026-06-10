from sqlalchemy import Boolean, Column, Float, Integer, String, Text, ForeignKey, DateTime
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
    nota = Column("Nota", Float, nullable=True)
    comentario = Column("Comentario", Text, nullable=True)
    avaliado_em = Column("AvaliadoEm", DateTime(timezone=True), server_default=func.now())

    json_raw = Column("JsonRaw", Text, nullable=True)
    json_raw_ia = Column("JsonRawIa", Text, nullable=True)
    aprovado_como_exemplo = Column("AprovadoComoExemplo", Boolean, default=False, nullable=False, index=True)
    aprovado_por = Column("AprovadoPor", String(150), nullable=True)
    aprovado_em = Column("AprovadoEm", DateTime(timezone=True), nullable=True)
    observacao_aprovacao = Column("ObservacaoAprovacao", Text, nullable=True)

    analisado_por = Column("AnalisadoPor", String(150), nullable=True, default="IA")
    corrigido_em = Column("CorrigidoEm", DateTime(timezone=True), nullable=True)

    protocolo = relationship("ChannelChatProtocol", back_populates="avaliacoes")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column("Nome", String(150), nullable=False)
    email = Column("Email", String(200), nullable=False, unique=True, index=True)
    senha_hash = Column("SenhaHash", String(255), nullable=False)
    criado_em = Column("CriadoEm", DateTime(timezone=True), server_default=func.now())


class CronEstado(Base):
    __tablename__ = "cron_estado"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fonte = Column("Fonte", String(500), nullable=False, unique=True, index=True)
    ultima_linha = Column("UltimaLinha", Integer, nullable=False, default=0)
    total_processados = Column("TotalProcessados", Integer, nullable=False, default=0)
    total_erros = Column("TotalErros", Integer, nullable=False, default=0)
    ultimo_erro = Column("UltimoErro", Text, nullable=True)
    atualizado_em = Column("AtualizadoEm", DateTime(timezone=True), nullable=True)


class CronConfig(Base):
    __tablename__ = "cron_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column("Url", Text, nullable=False, unique=True)
    nome = Column("Nome", String(150), nullable=True)
    ativo = Column("Ativo", Boolean, default=True, nullable=False)
    criado_por = Column("CriadoPor", String(150), nullable=True)
    criado_em = Column("CriadoEm", DateTime(timezone=True), server_default=func.now())


class CategoriaCustom(Base):
    __tablename__ = "categorias_custom"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column("Nome", String(100), nullable=False, unique=True, index=True)
    criada_por = Column("CriadaPor", String(150), nullable=True)
    criado_em = Column("CriadoEm", DateTime(timezone=True), server_default=func.now())


class GoldenDatasetItem(Base):
    __tablename__ = "golden_dataset_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    avaliacao_id = Column(
        "AvaliacaoId",
        Integer,
        ForeignKey("avaliacoes.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    texto = Column("Texto", Text, nullable=False)
    categoria_esperada = Column("CategoriaEsperada", String(100), nullable=True)
    sentimento_esperado = Column("SentimentoEsperado", String(50), nullable=True)
    criticidade_esperada = Column("CriticidadeEsperada", String(50), nullable=True)
    score_esperado = Column("ScoreEsperado", Float, nullable=True)
    incluido_por = Column("IncluidoPor", String(150), nullable=True)
    incluido_em = Column("IncluidoEm", DateTime(timezone=True), server_default=func.now())

    avaliacao = relationship("Avaliacao")


class GoldenDatasetRun(Base):
    __tablename__ = "golden_dataset_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    executado_em = Column("ExecutadoEm", DateTime(timezone=True), server_default=func.now())
    total_casos = Column("TotalCasos", Integer, nullable=False, default=0)
    acertos_categoria = Column("AcertosCategoria", Integer, nullable=False, default=0)
    acertos_sentimento = Column("AcertosSentimento", Integer, nullable=False, default=0)
    acertos_criticidade = Column("AcertosCriticidade", Integer, nullable=False, default=0)
    acuracia_geral = Column("AcuraciaGeral", Float, nullable=False, default=0.0)
    detalhes_json = Column("DetalhesJson", Text, nullable=True)
