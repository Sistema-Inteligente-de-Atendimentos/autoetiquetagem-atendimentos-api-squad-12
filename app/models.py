from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB  
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from config import Base 

class Atendimento(Base):
    __tablename__ = 'atendimentos' 
    id = Column(Integer, primary_key=True, autoincrement=True)
    texto_bruto = Column(Text, nullable=False)
    origem = Column(String(50)) 
    data_criacao = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    analises = relationship("AnaliseIA", back_populates="atendimento", cascade="all, delete-orphan")

class AnaliseIA(Base):
    __tablename__ = 'analises_ia'
    id = Column(Integer, primary_key=True, autoincrement=True)
    atendimento_id = Column(Integer, ForeignKey('atendimentos.id'), nullable=False, index=True)
    
    categoria = Column(String(100), index=True)
    intencao = Column(String(100))
    sentimento = Column(String(50), index=True)
    criticidade = Column(String(50), index=True)
    resumo = Column(Text)
    topicos = Column(JSONB) 
    json_raw = Column(Text) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    atendimento = relationship("Atendimento", back_populates="analises")
    score_qualidade = relationship("ScoreQualidade", back_populates="analise", uselist=False)
    validacoes = relationship("ValidacaoHumana", back_populates="analise")

class ScoreQualidade(Base):
    __tablename__ = 'scores_qualidade'
    id = Column(Integer, primary_key=True, autoincrement=True)
    analise_id = Column(Integer, ForeignKey('analises_ia.id'), nullable=False)
    
    empatia = Column(Integer)
    clareza = Column(Integer)
    objetividade = Column(Integer)
    resolutividade = Column(Integer)
    score_final = Column(Float)

    analise = relationship("AnaliseIA", back_populates="score_qualidade")

class ValidacaoHumana(Base):
    __tablename__ = 'validacoes_humana'
    id = Column(Integer, primary_key=True, autoincrement=True)
    analise_id = Column(Integer, ForeignKey('analises_ia.id'), nullable=False)
    
    categoria_correta = Column(String)
    sentimento_correto = Column(String)
    observacoes = Column(Text)
    usuario_revisor = Column(String)
    status = Column(String)
    data_validacao = Column(DateTime(timezone=True))

    analise = relationship("AnaliseIA", back_populates="validacoes")