import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey, Boolean, UniqueConstraint, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from enum import Enum as PyEnum
from sqlalchemy import Enum as SqlEnum

from shared.base import Base

class ContractType(str, PyEnum):
    CDI = "CDI"
    CDD = "CDD"
    STAGE = "STAGE"
    FREELANCE = "FREELANCE"

class OfferStatus(str, PyEnum):
    NEW = "NEW"
    ANALYZED = "ANALYZED"
    ARCHIVED = "ARCHIVED"

class SourceType(str, PyEnum):
    OFFICIAL_API = "OFFICIAL_API"
    SCRAPER = "SCRAPER"
    MOCK = "MOCK"

class RunStatus(str, PyEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"

class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[SourceType] = mapped_column(SqlEnum(SourceType))
    base_url: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class JobOffer(Base):
    __tablename__ = "job_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_sources.id", ondelete="CASCADE"))
    source_url: Mapped[str] = mapped_column(String(1000), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(300))
    location: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    description: Mapped[str] = mapped_column(String) # unlimited length text
    required_skills: Mapped[Optional[str]] = mapped_column(String, nullable=True) # JSON serialized or comma separated
    contract_type: Mapped[Optional[ContractType]] = mapped_column(SqlEnum(ContractType), nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[OfferStatus] = mapped_column(SqlEnum(OfferStatus), default=OfferStatus.NEW)
    required_certifications: Mapped[List[str]] = mapped_column(ARRAY(String(200)), default=list)
    preferred_certifications: Mapped[List[str]] = mapped_column(ARRAY(String(200)), default=list)

    def mark_as_analyzed(self):
        self.status = OfferStatus.ANALYZED

    def archive(self):
        self.status = OfferStatus.ARCHIVED

class JobOfferEmbedding(Base):
    __tablename__ = "job_offer_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_offers.id", ondelete="CASCADE"), unique=True)
    vector: Mapped[list[float]] = mapped_column(Vector(1024))
    model_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JobSkill(Base):
    __tablename__ = "job_skills"
    __table_args__ = (
        UniqueConstraint("job_offer_id", "skill_id", name="uq_job_offer_skill"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_offers.id", ondelete="CASCADE"))
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    importance: Mapped[str] = mapped_column(String(20), default="essential")  # 'essential' or 'nice_to_have'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_sources.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    offers_collected: Mapped[int] = mapped_column(default=0)
    status: Mapped[RunStatus] = mapped_column(SqlEnum(RunStatus))
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class CertificationStandard(Base):
    __tablename__ = "certification_standards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(200), unique=True)
    aliases: Mapped[List[str]] = mapped_column(ARRAY(String(200)), default=list)
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
