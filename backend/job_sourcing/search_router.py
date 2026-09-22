"""
POST /jobs/search — Unified search endpoint with AI Best-Match ranking & user preferences integration.

Phase A: Query local DB for matching offers (word-level OR filter).
Phase B: Query active connectors in parallel for fresh external discovery.
Phase C: Normalize + cross-source deduplicate + persist new offers to DB.
Phase D: Inject precomputed match scores & summaries from backend Match model for latest user CV.
Phase E: Rank combined results:
  - 'best_match' mode (DEFAULT): Scored jobs sorted by compatibility_score DESC, followed by unscored jobs (score=None remains None).
  - 'newest' mode: Jobs sorted by collected_at DESC.
"""
import uuid
import logging
from typing import List, Optional, Dict
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from shared.database import get_db
from user_management.dependencies import get_current_user
from user_management.models import User, UserPreferences
from job_sourcing.models import JobSource, JobOffer, ContractType

logger = logging.getLogger(__name__)

search_router = APIRouter(
    prefix="/jobs",
    tags=["jobs-search"],
    dependencies=[Depends(get_current_user)],
)

# ── Response schema ────────────────────────────────────────────
class JobSearchResult(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_name: Optional[str] = None   # human-readable source label
    source_url: str
    title: str
    company: str
    location: Optional[str] = None
    description: str
    required_skills: Optional[str] = None
    contract_type: Optional[ContractType] = None
    posted_at: Optional[datetime] = None
    collected_at: datetime
    compatibility_score: Optional[float] = None
    summary: Optional[str] = None       # Concise AI match explanation when available
    is_fresh: bool = False              # Always false since no fresh discovery in search endpoint

    class Config:
        from_attributes = True


# ── Main endpoint ──────────────────────────────────────────────
@search_router.post("/search", response_model=List[JobSearchResult])
def search_jobs(
    keywords: str = Query(..., min_length=1, max_length=120),
    contract_type: Optional[ContractType] = None,
    location: Optional[str] = None,
    sort_by: str = Query("best_match", pattern="^(best_match|newest)$"),
    limit: int = Query(40, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unified job search: local DB + fresh discovery from active sources.
    Ranks combined results:
      - 'best_match' mode: Scored jobs sorted by compatibility_score DESC, followed by unscored jobs (score=None).
      - 'newest' mode: Sorted by collected_at DESC.
    """
    from cv_management.models import CV
    from matching.models import Match

    # ── Preferences fallback for keywords/filters if empty ──────────
    prefs = db.query(UserPreferences).filter_by(user_id=current_user.id).first()
    search_keywords = keywords.strip()
    
    if not contract_type and prefs and prefs.preferred_contract_types:
        try:
            # Map first preferred contract type if valid
            contract_type = ContractType(prefs.preferred_contract_types[0])
        except ValueError:
            pass

    latest_cv = db.query(CV).filter_by(user_id=current_user.id).order_by(
        CV.created_at.desc()
    ).first()

    # ── Phase A: Local DB search ───────────────────────────────
    words = [w.strip() for w in search_keywords.split() if w.strip()]
    word_filters = []
    for w in words:
        w_term = f"%{w}%"
        word_filters.append(
            (JobOffer.title.ilike(w_term)) |
            (JobOffer.company.ilike(w_term)) |
            (JobOffer.description.ilike(w_term))
        )
    
    db_q = db.query(JobOffer).filter(or_(*word_filters)) if word_filters else db.query(JobOffer)
    if contract_type:
        db_q = db_q.filter(JobOffer.contract_type == contract_type)
    if location:
        db_q = db_q.filter(JobOffer.location.ilike(f"%{location}%"))

    # Include offers with pre-calculated matches for current user's CV
    matched_offer_ids = []
    if latest_cv:
        matched_offer_ids = [m.job_offer_id for m in db.query(Match.job_offer_id).filter_by(cv_id=latest_cv.id).all()]

    if matched_offer_ids:
        matched_offers = db.query(JobOffer).filter(JobOffer.id.in_(matched_offer_ids)).all()
        general_offers = db_q.order_by(JobOffer.collected_at.desc()).limit(limit).all()
        seen_ids = set()
        existing = []
        for o in (matched_offers + general_offers):
            if o.id not in seen_ids:
                seen_ids.add(o.id)
                existing.append(o)
    else:
        existing = db_q.order_by(JobOffer.collected_at.desc()).limit(limit).all()

    seen_fps: set = {o.fingerprint for o in existing}

    # ── Phase B: REMOVED - No synchronous network calls in search endpoint ──
    # Fresh discovery is handled by separate background processes, not by user search requests
    # This prevents timeout issues and ensures fast response times

    # ── Phase C: Inject precomputed match scores & summaries ──
    match_map: Dict[uuid.UUID, Match] = {}
    latest_cv = db.query(CV).filter_by(user_id=current_user.id).order_by(
        CV.created_at.desc()
    ).first()
    if latest_cv:
        matches = db.query(Match).filter_by(cv_id=latest_cv.id).all()
        match_map = {m.job_offer_id: m for m in matches}

    # ── Phase D: Build Response from existing data only ─────────
    source_id_to_name: Dict[uuid.UUID, str] = {s.id: s.name for s in db.query(JobSource).all()}
    
    results: List[JobSearchResult] = []
    for offer in existing:
        m = match_map.get(offer.id)
        results.append(JobSearchResult(
            id=offer.id,
            source_id=offer.source_id,
            source_name=source_id_to_name.get(offer.source_id, "platform"),
            source_url=offer.source_url,
            title=offer.title,
            company=offer.company,
            location=offer.location,
            description=offer.description,
            required_skills=offer.required_skills,
            contract_type=offer.contract_type,
            posted_at=offer.posted_at,
            collected_at=offer.collected_at,
            compatibility_score=m.compatibility_score if m else None,
            summary=m.summary if m else None,
            is_fresh=False,  # Always false since no fresh discovery in search endpoint
        ))

    # ── Phase E: Strict Ranking Rule ──────────────────────────
    if sort_by == "best_match" and latest_cv:
        # 1. Scored jobs sorted by compatibility_score DESC
        scored = [r for r in results if r.compatibility_score is not None]
        scored.sort(key=lambda r: r.compatibility_score, reverse=True)

        # 2. Unscored jobs follow afterward (never converted to 0)
        unscored = [r for r in results if r.compatibility_score is None]
        unscored.sort(key=lambda r: r.collected_at, reverse=True)

        results = (scored + unscored)[:limit]
    else:
        # Newest mode: sort by collected_at DESC
        results.sort(key=lambda r: r.collected_at, reverse=True)
        results = results[:limit]

    logger.info(
        f"search '{search_keywords}' ({sort_by}): {len(results)} total returned "
        f"({sum(1 for r in results if r.compatibility_score is not None)} scored)"
    )
    return results


# ── Backfill embeddings for existing offers ────────────────────
@search_router.post("/embed-missing")
def embed_missing_offers(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Admin-level endpoint: generate embeddings for JobOffers that are missing them.
    Processes up to `limit` offers per call. Returns counts.
    """
    from job_sourcing.models import JobOfferEmbedding

    offers_missing = (
        db.query(JobOffer)
        .outerjoin(JobOfferEmbedding, JobOffer.id == JobOfferEmbedding.job_offer_id)
        .filter(JobOfferEmbedding.id == None)
        .limit(limit)
        .all()
    )

    generated = 0
    failed = 0
    for offer in offers_missing:
        try:
            emb = JobEmbeddingService.generate_embedding(offer, db)
            db.add(emb)
            db.flush()
            generated += 1
        except Exception as e:
            logger.warning(f"embed-missing: failed for '{offer.title}': {e}")
            failed += 1

    db.commit()
    total_missing_remaining = (
        db.query(JobOffer)
        .outerjoin(JobOfferEmbedding, JobOffer.id == JobOfferEmbedding.job_offer_id)
        .filter(JobOfferEmbedding.id == None)
        .count()
    )
    return {
        "generated": generated,
        "failed": failed,
        "remaining_without_embedding": total_missing_remaining,
    }


class JobInventoryStatus(BaseModel):
    total_offers: int
    relevant_offers: int
    sourcing_active: bool
    last_collection_at: Optional[datetime] = None


@search_router.get("/status", response_model=JobInventoryStatus)
def get_inventory_status(
    keywords: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Lightweight diagnostic endpoint returning overall job inventory stats,
    user-relevant offer counts based on target roles/keywords,
    and active sourcing state without executing any matching or LLM calls.
    """
    from job_sourcing.models import CollectionRun
    from user_management.models import UserPreferences

    total = db.query(JobOffer).count()
    active_run = db.query(CollectionRun).filter(CollectionRun.finished_at == None).first()
    last_run = db.query(CollectionRun).order_by(CollectionRun.started_at.desc()).first()

    last_at = None
    if last_run:
        last_at = last_run.finished_at or last_run.started_at

    # Determine relevance criteria for current user
    kw_phrases = []
    if keywords and keywords.strip():
        kw_phrases.append(keywords.strip())
    else:
        prefs = db.query(UserPreferences).filter_by(user_id=current_user.id).first()
        if prefs:
            if prefs.target_roles:
                kw_phrases.extend(prefs.target_roles)
            elif prefs.job_keywords:
                kw_phrases.append(prefs.job_keywords)

    relevant_count = total
    if kw_phrases:
        phrase_conds = []
        for phrase in kw_phrases:
            words = [
                w.strip().lower()
                for w in phrase.replace("/", " ").replace("-", " ").split()
                if len(w.strip()) > 1 and w.strip().lower() not in {"and", "for", "the", "with", "in", "at"}
            ]
            if words:
                phrase_conds.append(
                    and_(*(
                        (JobOffer.title.ilike(f"%{w}%")) | (JobOffer.required_skills.ilike(f"%{w}%"))
                        for w in words
                    ))
                )

        if phrase_conds:
            relevant_count = db.query(JobOffer).filter(or_(*phrase_conds)).count()
        else:
            relevant_count = total

    return JobInventoryStatus(
        total_offers=total,
        relevant_offers=relevant_count,
        sourcing_active=bool(active_run),
        last_collection_at=last_at
    )
