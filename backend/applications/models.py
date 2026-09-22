import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Enum, Text, Boolean, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from shared.base import Base

# Ensure foreign key target models are registered in Base metadata
import user_management.models  # noqa: F401 (users table)
import job_sourcing.models     # noqa: F401 (job_offers table)
import matching.models         # noqa: F401 (matches table)


class ApplicationMode(str, PyEnum):
    MANUAL_VALIDATION = "MANUAL_VALIDATION"
    ASSISTED = "ASSISTED"
    FULL_AUTO = "FULL_AUTO"

class ApplicationStatus(str, PyEnum):
    DRAFT = "DRAFT"
    PENDING_VALIDATION = "PENDING_VALIDATION"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUBMITTING = "SUBMITTING"
    SENT = "SENT"
    FAILED = "FAILED"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"
    ACTION_REQUIRED = "ACTION_REQUIRED"

class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_offer_id", name="uq_user_job_application"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_offers.id", ondelete="RESTRICT"), index=True, nullable=False)
    match_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("matches.id", ondelete="SET NULL"), index=True, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
    mode: Mapped[ApplicationMode] = mapped_column(Enum(ApplicationMode), default=ApplicationMode.MANUAL_VALIDATION)
    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus), default=ApplicationStatus.PENDING_VALIDATION)
    
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_logs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    screenshots: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    pending_questions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    user_responses: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def approve(self):
        if self.status != ApplicationStatus.PENDING_VALIDATION:
            raise ValueError(f"Cannot approve application in status: {self.status}")
        self.status = ApplicationStatus.APPROVED

    def reject(self, reason: Optional[str] = None):
        if self.status != ApplicationStatus.PENDING_VALIDATION:
            raise ValueError(f"Cannot reject application in status: {self.status}")
        self.status = ApplicationStatus.REJECTED
        self.failure_reason = reason

    def mark_as_sent(self):
        self.status = ApplicationStatus.SENT
        self.submitted_at = datetime.utcnow()
        self.failure_reason = None

    def mark_as_failed(self, reason: str):
        self.status = ApplicationStatus.FAILED
        self.failure_reason = reason

    def mark_as_manual_required(self, reason: str):
        self.status = ApplicationStatus.MANUAL_REQUIRED
        self.failure_reason = reason


class AgentActivityLog(Base):
    """
    Log of actions taken autonomously or recommend-mode actions performed by the AI Recruitment Agent.
    """
    __tablename__ = "agent_activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(100))  # e.g., 'EVALUATED_OPPORTUNITY', 'AUTO_APPLIED', 'SKIPPED_LIMIT', 'SKIPPED_SCORE'
    message: Mapped[str] = mapped_column(Text)
    job_offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("job_offers.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

