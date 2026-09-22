import uuid
import threading
from datetime import datetime, timedelta
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from shared.database import get_db
from user_management.dependencies import get_current_user
from user_management.models import User
from job_sourcing.models import CollectionRun

from matching.schemas import (
    MatchResponse,
    MatchingConfigResponse,
    MatchingConfigUpdate,
)
from matching.matching_service import MatchingService
from matching.services.recommendation_service import RecommendationService
from matching.adapters.cosine_similarity_calculator import PgVectorSimilarityCalculator
from matching.adapters.groq_matching_evaluator import GroqMatchingEvaluator

router = APIRouter(prefix="/matching", tags=["matching"])

# Idempotency guard for trigger-sourcing.
# Uses a per-user cooldown timestamp (2 minutes) held under a lock.
# This is intentionally the only guard — it is immune to background-task
# timing because the timestamp is set before the task is enqueued and is
# never cleared by the task itself.
_sourcing_lock = threading.Lock()
_last_sourcing_time: Dict[str, datetime] = {}   # keyed by str(user_id)

# Instantiate adapters as singletons
similarity_calculator = PgVectorSimilarityCalculator()
llm_evaluator = GroqMatchingEvaluator()

@router.get("/cv/{cv_id}/job/{job_offer_id}", response_model=MatchResponse)
def get_match_explanation(cv_id: uuid.UUID, job_offer_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return a computed user-owned match without triggering LLM work."""
    from cv_management.models import CV
    from matching.models import Match
    cv = db.get(CV, cv_id)
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trouvé")
    if cv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès non autorisé")
    match = db.query(Match).filter_by(cv_id=cv_id, job_offer_id=job_offer_id).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match non calculé")
    return match


@router.post("/cv/{cv_id}/job/{job_offer_id}", response_model=MatchResponse)
def compute_single_match(
    cv_id: uuid.UUID,
    job_offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compute (or recalculate) the matching score and qualitative breakdown between a CV and a Job Offer.
    """
    match = MatchingService.compute_match(
        cv_id=cv_id,
        job_offer_id=job_offer_id,
        user_id=current_user.id,
        similarity_calculator=similarity_calculator,
        llm_evaluator=llm_evaluator,
        db=db,
    )
    return match


@router.get("/cv/{cv_id}/best-matches", response_model=List[MatchResponse])
def get_best_matches_for_cv(
    cv_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get top matching job offers for a specific CV sorted by compatibility score.
    """
    ranked_pairs = MatchingService.get_best_matches_for_cv(
        cv_id=cv_id,
        user_id=current_user.id,
        similarity_calculator=similarity_calculator,
        llm_evaluator=llm_evaluator,
        db=db,
        limit=limit,
        offset=offset,
    )

    response_list = []
    for match, job_offer in ranked_pairs:
        resp = MatchResponse.model_validate(match)
        resp.job_offer = {
            "id": str(job_offer.id),
            "title": job_offer.title,
            "company": job_offer.company,
            "location": job_offer.location,
            "source_url": job_offer.source_url,
            "contract_type": job_offer.contract_type.value if job_offer.contract_type else None,
            "posted_at": job_offer.posted_at.isoformat() if job_offer.posted_at else None,
        }
        response_list.append(resp)

    return response_list


@router.get("/config", response_model=MatchingConfigResponse)
def get_matching_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's matching configuration.
    The 6-factor scoring uses fixed weights and does not require user configuration.
    """
    config = MatchingService.get_or_create_config(current_user.id, db)
    return config


@router.put("/config", response_model=MatchingConfigResponse)
def update_matching_config(
    payload: MatchingConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update current user's matching configuration.
    The 6-factor scoring uses fixed weights, so this endpoint currently returns the existing config.
    """
    config = MatchingService.get_or_create_config(current_user.id, db)
    # No configuration fields to update - 6-factor scoring uses fixed weights
    db.commit()
    db.refresh(config)
    return config


@router.get("/cv/{cv_id}/auto-recommendations")
def get_auto_recommendations(
    cv_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get auto-generated recommendations for a CV.
    
    This endpoint wraps the RecommendationService which sits above MatchingService.
    It adds recommendation-level classification (HIGHLY_RECOMMENDED, RECOMMENDED, etc.)
    to the existing matching results.
    """
    recommendations = RecommendationService.get_recommendations_for_cv(
        cv_id=cv_id,
        user_id=current_user.id,
        similarity_calculator=similarity_calculator,
        llm_evaluator=llm_evaluator,
        db=db,
        limit=limit,
        offset=offset
    )
    
    # Convert to response format
    response_list = []
    for match_dict, job_offer_dict in recommendations:
        response_list.append({
            "match": match_dict,
            "job_offer": job_offer_dict
        })
    
    return response_list


@router.post("/cv/{cv_id}/trigger-sourcing", status_code=status.HTTP_202_ACCEPTED)
def trigger_user_job_sourcing(
    cv_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger background job sourcing tailored to candidate's target roles and preferences.
    Idempotent: prevents duplicate or rapid concurrent collection triggers.
    Responds immediately with 202 Accepted.
    """
    from cv_management.models import CV
    from user_management.models import UserPreferences
    from job_sourcing.models import JobSource
    from job_sourcing.services.collection_service import JobCollectionService

    cv = db.get(CV, cv_id)
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trouvé")
    if cv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès non autorisé")

    prefs = db.query(UserPreferences).filter_by(user_id=current_user.id).first()
    keywords_list = []
    if prefs and prefs.target_roles:
        keywords_list.extend(prefs.target_roles)
    if prefs and prefs.job_keywords and not keywords_list:
        keywords_list.append(prefs.job_keywords)
    
    if not keywords_list:
        keywords_list = ["developer", "devops", "software engineer"]

    query_str = " ".join(keywords_list)
    uid_key = str(current_user.id)

    with _sourcing_lock:
        now = datetime.utcnow()

        # Cooldown guard — blocks duplicate triggers for 2 minutes.
        # Also doubles as a DB guard: if a real collection was already
        # running it would have been triggered recently as well.
        last_at = _last_sourcing_time.get(uid_key)
        if last_at and (now - last_at) < timedelta(minutes=2):
            return {
                "status": "sourcing_already_active",
                "keywords": query_str,
                "message": "Une collecte d'opportunités a été récemment lancée. Veuillez patienter."
            }

        # DB guard: an existing active CollectionRun means another process is collecting
        active_db_run = db.query(CollectionRun).filter(CollectionRun.finished_at == None).first()
        if active_db_run:
            return {
                "status": "sourcing_already_active",
                "keywords": query_str,
                "message": "Une collecte d'opportunités est actuellement en cours sur la plateforme."
            }

        # Stamp the timestamp while holding the lock, before the task starts
        _last_sourcing_time[uid_key] = now

    def _bg_run_sourcing(kw: str):
        from shared.database import SessionLocal
        import logging
        task_logger = logging.getLogger(__name__)
        task_db = SessionLocal()
        try:
            active_sources = task_db.query(JobSource).filter_by(is_active=True).all()
            for src in active_sources:
                try:
                    JobCollectionService.run_collection(src, kw, task_db)
                except Exception as err:
                    task_logger.warning(f"Background user sourcing failed for {src.name}: {err}")
        finally:
            task_db.close()

    background_tasks.add_task(_bg_run_sourcing, query_str)
    return {
        "status": "sourcing_queued",
        "keywords": query_str,
        "message": f"Sourcing lancé en arrière-plan pour : {query_str}"
    }
