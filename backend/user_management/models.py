import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Text, ForeignKey, ARRAY, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from shared.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)  # Required for email auth
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Note: Database schema is simplified - only the above fields exist
    # No updated_at, is_verified, full_name, avatar_url, timezone, language, email_notifications
    # No OAuth fields, verification fields, password reset fields, or 2FA fields
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreferences", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("UserPasswordReset", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    refresh_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    user = relationship("User", back_populates="sessions")


class UserActivity(Base):
    __tablename__ = "user_activities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100))  # 'login', 'logout', 'password_change', etc.
    description: Mapped[str] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="activities")


class UserPreferences(Base):
    """
    User job search preferences for personalized recommendations, job sourcing, and AI Agent autonomy.
    """
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    
    # Job search preferences ("WHAT DOES THE CANDIDATE WANT?")
    job_keywords: Mapped[str] = mapped_column(String(500), default="developer python react javascript")
    preferred_locations: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)
    preferred_contract_types: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    remote_preference: Mapped[bool] = mapped_column(Boolean, default=False)  # true=remote only, false=onsite (allows hybrid)
    min_salary: Mapped[int] = mapped_column(Integer, nullable=True)  # Minimum annual salary in EUR
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)

    # AI Agent Preferences ("HOW MUCH AUTONOMY SHOULD THE AGENT HAVE?")
    application_mode: Mapped[str] = mapped_column(String(50), default="RECOMMEND_ONLY")  # RECOMMEND_ONLY or AUTO_APPLY
    min_match_score: Mapped[float] = mapped_column(default=80.0)  # Min compatibility score for auto-apply
    max_applications_per_day: Mapped[int] = mapped_column(Integer, default=5)  # Daily application limit
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="preferences")


class UserPasswordReset(Base):
    """
    Stores secure one-time tokens for the password reset flow.
    Each token expires after 1 hour and can only be used once.
    """
    __tablename__ = "user_password_resets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="password_resets")
