import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column
from shared.base import Base

class NotificationType(str, PyEnum):
    APPLICATION_SENT = "APPLICATION_SENT"
    APPLICATION_FAILED = "APPLICATION_FAILED"
    NEW_MATCH = "NEW_MATCH"
    ACTION_REQUIRED = "ACTION_REQUIRED"

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    message: Mapped[str] = mapped_column(Text)
    
    related_application_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
