import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from applications.models import ApplicationMode, ApplicationStatus

class ApplicationResponse(BaseModel):
    id: uuid.UUID
    job_offer_id: uuid.UUID
    match_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    mode: ApplicationMode
    status: ApplicationStatus
    submitted_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    cover_letter: Optional[str] = None
    execution_logs: Optional[Any] = None
    screenshots: Optional[Any] = None
    pending_questions: Optional[Any] = None
    user_responses: Optional[Any] = None
    created_at: datetime
    
    # Nested info optionally populated in router/services
    match_details: Optional[Any] = None

    class Config:
        from_attributes = True

class CoverLetterResponse(BaseModel):
    application_id: uuid.UUID
    cover_letter: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None

class CoverLetterUpdate(BaseModel):
    cover_letter: str = Field(..., min_length=10, description="Cover letter content (minimum 10 characters)")

class AnswerQuestionsRequest(BaseModel):
    answers: dict = Field(..., description="Dictionary of question IDs to user answers")

class ActionRequiredDetails(BaseModel):
    application_id: uuid.UUID
    action_reason: Optional[str] = None
    screenshots: Optional[Any] = None
    execution_logs: Optional[Any] = None
    pending_questions: Optional[Any] = None
    job_offer_url: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
