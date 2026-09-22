import uuid
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, model_validator


class MatchAssessmentData(BaseModel):
    """
    Pydantic schema to validate the JSON structure returned by the LLM (Groq).
    """
    matching_points: List[str] = Field(default_factory=list, description="Strengths and matching skills")
    gap_points: List[str] = Field(default_factory=list, description="Missing skills or experience gaps")
    summary: str = Field(..., description="Short 1-2 sentence match justification")
    score: int = Field(..., ge=0, le=100, description="Overall compatibility score from 0 to 100")


class MatchResponse(BaseModel):
    """
    API Response schema for a Match object with 6-factor scoring.
    """
    id: uuid.UUID
    cv_id: uuid.UUID
    job_offer_id: uuid.UUID

    # Original fields (for backward compatibility)
    semantic_similarity: float
    llm_score: float
    compatibility_score: float

    # New 6-factor scoring components
    skills_score: float = 0.0
    experience_score: float = 0.0
    seniority_score: float = 0.0
    semantic_score: float = 0.0
    certification_bonus: float = 0.0

    matching_points: List[str]
    gap_points: List[str]
    summary: Optional[str] = None
    computed_at: datetime

    # Optional nested details for list responses
    job_offer: Optional[Any] = None
    cv_info: Optional[Any] = None

    class Config:
        from_attributes = True


class MatchingConfigResponse(BaseModel):
    """
    API Response schema for MatchingConfig.
    The 6-factor scoring uses fixed weights and does not require user configuration.
    """
    id: uuid.UUID
    user_id: uuid.UUID

    class Config:
        from_attributes = True


class MatchingConfigUpdate(BaseModel):
    """
    Request payload to update MatchingConfig.
    The 6-factor scoring uses fixed weights, so no configuration fields are currently needed.
    This schema is kept for API compatibility but does not process any fields.
    """
    pass
