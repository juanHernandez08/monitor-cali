import datetime as dt
import enum

from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, DateTime, Float,
    JSON, UniqueConstraint, Enum,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SourceType(enum.Enum):
    RSS = "rss"
    REDDIT = "reddit"
    SERP = "serp"
    RADIO = "radio"


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
    author = Column(String, nullable=True)
    text = Column(String, nullable=False)
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
    model = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    mention = relationship("Mention", back_populates="sentiment")
