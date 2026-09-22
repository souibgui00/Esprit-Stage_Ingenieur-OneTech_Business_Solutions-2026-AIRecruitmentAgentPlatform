from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from shared.database import get_db
from user_management.dependencies import get_current_user
from user_management.models import User
from cv_management.models import CV
from applications.application_service import ApplicationService
from notifications.services import NotificationService
from matching.models import Match
from job_sourcing.models import JobOffer

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/summary")
def get_candidate_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Candidate-scoped home data only; no synthetic recommendations or counts."""
    cv = db.query(CV).filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    applications = ApplicationService.get_applications(db, current_user.id, None)[:5]
    notifications = NotificationService.get_notifications(db, current_user.id)[:5]
    recommendations = []
    if cv:
        rows = (db.query(Match, JobOffer).join(JobOffer, Match.job_offer_id == JobOffer.id)
                .filter(Match.cv_id == cv.id).order_by(Match.compatibility_score.desc()).limit(4).all())
        recommendations = [{
            "match": {"id": str(match.id), "job_offer_id": str(match.job_offer_id),
                      "compatibility_score": match.compatibility_score,
                      "matching_points": match.matching_points or [], "gap_points": match.gap_points or [],
                      "summary": match.summary},
            "job_offer": {"id": str(job.id), "title": job.title, "company": job.company,
                          "location": job.location, "source_url": job.source_url,
                          "contract_type": job.contract_type.value if job.contract_type else None,
                          "posted_at": job.posted_at.isoformat() if job.posted_at else None},
        } for match, job in rows]
    return {"cv": cv, "recommendations": recommendations, "applications": applications, "notifications": notifications}
