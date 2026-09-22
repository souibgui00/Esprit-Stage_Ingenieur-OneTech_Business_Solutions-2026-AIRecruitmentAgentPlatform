import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from user_management.dependencies import get_current_user
from user_management.models import User
from job_sourcing.models import JobSource, JobOffer, CollectionRun, ContractType, OfferStatus
from job_sourcing.schemas import (
    JobSourceCreate,
    JobSourceResponse,
    JobOfferResponse,
    CollectionRunResponse
)
from job_sourcing.services.collection_service import JobCollectionService
from matching.matching_service import MatchingService
# Import connectors package to trigger registration on boot
import job_sourcing.connectors 

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(get_current_user)] # Protect all endpoints in this router
)

@router.post("/sources", response_model=JobSourceResponse, status_code=status.HTTP_201_CREATED)
def create_job_source(source_in: JobSourceCreate, db: Session = Depends(get_db)):
    """Create a new job search source platform configuration."""
    db_source = JobSource(
        name=source_in.name,
        type=source_in.type,
        base_url=source_in.base_url,
        is_active=source_in.is_active
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source

@router.get("/sources", response_model=List[JobSourceResponse])
def list_job_sources(db: Session = Depends(get_db)):
    """List all registered job search platforms."""
    return db.query(JobSource).all()

def _bg_collect(source_id: uuid.UUID, keywords: str):
    """Worker function executed inside FastAPI BackgroundTasks."""
    # Obtain a new database session for the background task
    from shared.database import SessionLocal
    db = SessionLocal()
    try:
        source = db.query(JobSource).filter_by(id=source_id).first()
        if source:
            JobCollectionService.run_collection(source, keywords, db)
    finally:
        db.close()

@router.post("/sources/{source_id}/collect", status_code=status.HTTP_202_ACCEPTED)
def trigger_collection(
    source_id: uuid.UUID,
    keywords: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger collection run asynchronously.
    Responds immediately with 202 Accepted.
    """
    source = db.query(JobSource).filter_by(id=source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Job source not found")
        
    if not source.is_active:
        raise HTTPException(status_code=400, detail="Job source is disabled")
        
    # Queue the collection task to run in the background
    background_tasks.add_task(_bg_collect, source_id, keywords)
    
    return {"message": "Job collection task successfully queued.", "status": "queued"}

@router.get("/runs", response_model=List[CollectionRunResponse])
def list_collection_runs(db: Session = Depends(get_db)):
    """List details of all historical collection runs."""
    return db.query(CollectionRun).order_by(CollectionRun.started_at.desc()).all()

@router.get("/offers", response_model=List[JobOfferResponse])
def list_job_offers(
    search: Optional[str] = Query(None, min_length=1, max_length=120),
    contract_type: Optional[ContractType] = None,
    location: Optional[str] = None,
    company: Optional[str] = None,
    status: Optional[OfferStatus] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Filter and fetch all collected job offers with pagination, joining precomputed match scores if available."""
    # Find user's latest CV to join match scores
    from cv_management.models import CV
    from matching.models import Match
    
    latest_cv = db.query(CV).filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    
    query = db.query(JobOffer)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (JobOffer.title.ilike(term)) |
            (JobOffer.company.ilike(term)) |
            (JobOffer.description.ilike(term))
        )
    
    if contract_type:
        query = query.filter(JobOffer.contract_type == contract_type)
    if location:
        query = query.filter(JobOffer.location.ilike(f"%{location}%"))
    if company:
        query = query.filter(JobOffer.company.ilike(f"%{company}%"))
    if status:
        query = query.filter(JobOffer.status == status)
        
    offers = query.order_by(JobOffer.collected_at.desc()).offset(offset).limit(limit).all()
    
    # Inject match scores if CV exists
    if latest_cv:
        # Load all matches for this CV
        matches = db.query(Match).filter_by(cv_id=latest_cv.id).all()
        match_map = {m.job_offer_id: m.compatibility_score for m in matches}
        for o in offers:
            o.compatibility_score = match_map.get(o.id)
            
    return offers

@router.get("/offers/{offer_id}", response_model=JobOfferResponse)
def get_job_offer(offer_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve full details of a specific job offer by ID."""
    offer = db.query(JobOffer).filter_by(id=offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Job offer not found")
    return offer
