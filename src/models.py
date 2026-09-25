import datetime as dt
import enum

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Float,
    JSON, UniqueConstraint, Enum,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SourceType(enum.Enum):
    RSS = "rss"
    REDDIT = "reddit"
    SERP = "serp"
    RADIO = "radio"
    GOOGLE_NEWS = "google_news"
    YOUTUBE = "youtube"
    GOOGLE_CSE = "google_cse"
    SOCIAL = "social"  # Instagram/Facebook por cuenta conocida (Bright Data)


class SentimentLabel(enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    party = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    aliases = Column(JSON, default=list)
    exclusions = Column(JSON, default=list)  # frases que identifican homónimos ("Arias Orjuela")
    kind = Column(String, default="candidate", nullable=False)  # "candidate" | "councilor" | "city"
    council = Column(Boolean, default=False, nullable=False)  # pertenece al Concejo de Cali
    context_terms = Column(JSON, default=list)  # si está, el texto debe contener alguno (nombres comunes)

    mentions = relationship("Mention", back_populates="candidate")


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(SourceType), nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSON, default=dict)

    mentions = relationship("Mention", back_populates="source")

    __table_args__ = (UniqueConstraint("type", "name", name="uq_source_type_name"),)


class Mention(Base):
    __tablename__ = "mentions"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    external_id = Column(String, nullable=False)
    url = Column(String, nullable=True)
    url_normalized = Column(String, nullable=True, index=True)
    author = Column(String, nullable=True)
    text = Column(String, nullable=False)  # titular / snippet / comentario
    body = Column(Text, nullable=True)  # cuerpo del artículo (None = pendiente, '' = no disponible)
    relevant = Column(Boolean, default=True, nullable=False)  # False = homónimo u otro descarte
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    raw = Column(JSON, default=dict)

    candidate = relationship("Candidate", back_populates="mentions")
    source = relationship("Source", back_populates="mentions")
    sentiment = relationship("SentimentScore", back_populates="mention", uselist=False)

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_mention_source_external"),
    )


class SentimentScore(Base):
    __tablename__ = "sentiment_scores"

    id = Column(Integer, primary_key=True)
    mention_id = Column(Integer, ForeignKey("mentions.id"), nullable=False, unique=True)
    label = Column(Enum(SentimentLabel), nullable=False)
    score = Column(Float, nullable=False)  # -1.0 a 1.0
    topic = Column(String, nullable=True)
    category = Column(String, nullable=True)  # categoría fija (ver sentiment.CATEGORIES)
    summary = Column(String, nullable=True)  # una frase: de qué trata, sin abrir la publicación
    model = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    mention = relationship("Mention", back_populates="sentiment")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    started_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    new_mentions = Column(Integer, default=0, nullable=False)
    error = Column(String, nullable=True)

    source = relationship("Source")


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True)
    service = Column(String, nullable=False)
    day = Column(String, nullable=False)  # YYYY-MM-DD (UTC)
    count = Column(Integer, default=0, nullable=False)

    __table_args__ = (UniqueConstraint("service", "day", name="uq_api_usage_service_day"),)
