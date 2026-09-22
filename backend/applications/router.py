import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from shared.database import get_db, SessionLocal
from user_management.dependencies import get_current_user
from user_management.models import User
from matching.models import Match
from job_sourcing.models import JobOffer
from applications.schemas import ApplicationResponse, CoverLetterResponse, CoverLetterUpdate, ActionRequiredDetails, AnswerQuestionsRequest
from applications.models import ApplicationStatus, Application, ApplicationMode
from applications.application_service import ApplicationService
from applications.adapters.playwright_application_channel import PlaywrightApplicationChannel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["applications"])

# Shared Playwright channel adapter
playwright_channel = PlaywrightApplicationChannel()

def _enrich_application(app, db: Session):
    # Retrieve match and job details for nested response enrichment
    match = db.get(Match, app.match_id) if app.match_id else None
    job_offer_id = getattr(app, "job_offer_id", None) or (match.job_offer_id if match else None)
    job_offer = db.get(JobOffer, job_offer_id) if job_offer_id else None
    app.match_details = {
        "compatibility_score": match.compatibility_score if match else None,
        "job_title": job_offer.title if job_offer else "Offre inconnue",
        "company": job_offer.company if job_offer else "Entreprise inconnue",
        "location": job_offer.location if job_offer else "Non précisé",
        "source_url": job_offer.source_url if job_offer else None,
        "job_offer_id": str(job_offer_id) if job_offer_id else None
    }
    return app

@router.post("/from-match/{match_id}", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application_from_match(
    match_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crée une candidature à partir d'un match calculé (auto-apply ou manuel).
    Phase 2: Submission moved to background execution for FULL_AUTO mode.
    """
    app = ApplicationService.process_match(
        match_id=match_id,
        user_id=current_user.id,
        application_channel=playwright_channel,
        db=db
    )
    
    # Phase 2: If mode is FULL_AUTO, execute submission in background
    if app.mode == ApplicationMode.FULL_AUTO and app.status == ApplicationStatus.SUBMITTING:
        background_tasks.add_task(_execute_submission_background, app.id, current_user.id)
    
    return _enrich_application(app, db)

@router.get("", response_model=List[ApplicationResponse])
def list_applications(
    status_filter: Optional[ApplicationStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Liste toutes les candidatures de l'utilisateur avec filtre optionnel par statut.
    """
    apps = ApplicationService.get_applications(db, current_user.id, status_filter)
    enriched_apps = [_enrich_application(app, db) for app in apps]
    return enriched_apps



# Background task wrappers to execute Playwright agent with isolated DB sessions
def _execute_submission_background(application_id: uuid.UUID, user_id: uuid.UUID):
    db = SessionLocal()
    try:
        ApplicationService.execute_submission(
            application_id=application_id,
            user_id=user_id,
            application_channel=playwright_channel,
            db=db
        )
    except Exception as e:
        print(f"Background submission failed for app {application_id}: {e}")
    finally:
        db.close()

def _run_agent_background(application_id: uuid.UUID, user_id: uuid.UUID):
    db = SessionLocal()
    try:
        ApplicationService.run_agent(
            application_id=application_id,
            user_id=user_id,
            application_channel=playwright_channel,
            db=db
        )
    except Exception as e:
        print(f"Background run_agent failed for app {application_id}: {e}")
    finally:
        db.close()

def _approve_application_background(application_id: uuid.UUID, user_id: uuid.UUID):
    db = SessionLocal()
    try:
        # Phase 3: Execute submission instead of approve_application
        ApplicationService.execute_submission(
            application_id=application_id,
            user_id=user_id,
            application_channel=playwright_channel,
            db=db
        )
    except Exception as e:
        print(f"Background submission failed for app {application_id}: {e}")
    finally:
        db.close()

@router.post("/{id}/approve", response_model=ApplicationResponse)
def approve_application(
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Approuve manuellement une candidature en attente et déclenche l'agent Playwright en tâche de fond.
    Phase 3: No longer executes Playwright synchronously, only transitions to APPROVED status.
    """
    app = ApplicationService.approve_application(
        application_id=id,
        user_id=current_user.id,
        db=db
    )
    
    # Schedule background submission after approval
    background_tasks.add_task(_approve_application_background, app.id, current_user.id)
    return _enrich_application(app, db)

@router.post("/{id}/reject", response_model=ApplicationResponse)
def reject_application(
    id: uuid.UUID,
    reason_payload: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rejette manuellement une candidature en attente.
    """
    reason = reason_payload.get("reason") if reason_payload else None
    app = ApplicationService.reject_application(
        application_id=id,
        user_id=current_user.id,
        reason=reason,
        db=db
    )
    return _enrich_application(app, db)

@router.post("/{id}/run-agent", response_model=ApplicationResponse)
def run_agent_for_application(
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exécute l'Agent Web Playwright sur une candidature en tâche de fond.
    """
    app = db.get(Application, id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")
    if app.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès non autorisé")

    # Force temporary status back to APPROVED to signal background processing
    app.status = ApplicationStatus.APPROVED
    db.commit()
    db.refresh(app)

    background_tasks.add_task(_run_agent_background, app.id, current_user.id)
    return _enrich_application(app, db)


# ── Cover Letter Management Endpoints (Phase 3) ────────────────

@router.get("/{id}/cover-letter", response_model=CoverLetterResponse)
def get_cover_letter(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère la lettre de motivation d'une candidature.
    Phase 3: Allows review before submission in Assisted mode.
    """
    app = db.get(Application, id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")
    if app.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès non autorisé")

    # Get job details for context
    job_offer = db.get(JobOffer, app.job_offer_id) if app.job_offer_id else None
    
    return CoverLetterResponse(
        application_id=app.id,
        cover_letter=app.cover_letter,
        job_title=job_offer.title if job_offer else None,
        company=job_offer.company if job_offer else None
    )

@router.post("/{id}/cover-letter/generate", response_model=ApplicationResponse)
def generate_cover_letter(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Génère une lettre de motivation pour une candidature sans déclencher la soumission.
    Phase 3: Allows pre-submission review in Assisted mode.
    """
    app = ApplicationService.generate_cover_letter_for_application(
        application_id=id,
        user_id=current_user.id,
        db=db
    )
    return _enrich_application(app, db)

@router.put("/{id}/cover-letter", response_model=ApplicationResponse)
def update_cover_letter(
    id: uuid.UUID,
    payload: CoverLetterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Met à jour la lettre de motivation d'une candidature.
    Phase 3: Allows manual editing before submission.
    """
    app = ApplicationService.update_cover_letter(
        application_id=id,
        user_id=current_user.id,
        cover_letter_content=payload.cover_letter,
        db=db
    )
    return _enrich_application(app, db)


# ── Action Required Details Endpoint (Phase 3) ───────────────────────

@router.get("/{id}/action-details", response_model=ActionRequiredDetails)
def get_action_required_details(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les détails d'une candidature nécessitant une intervention humaine.
    Phase 3: Provides CAPTCHA/manual intervention information.
    """
    app = db.get(Application, id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")
    if app.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès non autorisé")

    if app.status != ApplicationStatus.ACTION_REQUIRED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette candidature ne nécessite pas d'intervention humaine."
        )

    # Get job details
    job_offer = db.get(JobOffer, app.job_offer_id) if app.job_offer_id else None
    
    return ActionRequiredDetails(
        application_id=app.id,
        action_reason=app.failure_reason,
        screenshots=app.screenshots,
        execution_logs=app.execution_logs,
        pending_questions=app.pending_questions,
        job_offer_url=job_offer.source_url if job_offer else None,
        job_title=job_offer.title if job_offer else None,
        company=job_offer.company if job_offer else None
    )


@router.post("/{id}/answer-questions", response_model=ApplicationResponse)
def answer_questions(
    id: uuid.UUID,
    payload: AnswerQuestionsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Accept user answers for pending questions and resume the application process.
    """
    app = ApplicationService.answer_questions(
        application_id=id,
        user_id=current_user.id,
        answers=payload.answers,
        application_channel=playwright_channel,
        db=db
    )
    background_tasks.add_task(_execute_submission_background, app.id, current_user.id)
    return _enrich_application(app, db)






# ── Decision Engine & Agent Activity Endpoints ────────────────

@router.get("/eligibility/{job_offer_id}")
def check_job_eligibility(
    job_offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Evaluates whether an opportunity is eligible for automatic application
    based on match score, candidate preferences, duplicate protection, daily limit, and autonomy rules.
    """
    from applications.decision_service import ApplicationDecisionService
    return ApplicationDecisionService.evaluate_eligibility(current_user.id, job_offer_id, db)


@router.post("/auto-apply-run")
def run_auto_apply_cycle(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Triggers an autonomous agent evaluation cycle over candidate's top matched opportunities.
    If application_mode is AUTO_APPLY and all eligibility rules pass, submits applications up to daily limit.
    Logs activity for user transparency.
    """
    from cv_management.models import CV
    from user_management.models import UserPreferences
    from applications.decision_service import ApplicationDecisionService
    from applications.models import AgentActivityLog

    latest_cv = (
        db.query(CV)
        .filter_by(user_id=current_user.id, status="PARSED")
        .order_by(CV.created_at.desc())
        .first()
    )
    if not latest_cv:
        return {"status": "NO_CV", "applied_count": 0, "message": "No parsed CV found."}

    # Fetch best matches
    from matching.adapters.cosine_similarity_calculator import PgVectorSimilarityCalculator
    from matching.adapters.groq_matching_evaluator import GroqMatchingEvaluator
    from matching.matching_service import MatchingService

    matches_with_jobs = MatchingService.get_best_matches_for_cv(
        cv_id=latest_cv.id,
        user_id=current_user.id,
        similarity_calculator=PgVectorSimilarityCalculator(),
        llm_evaluator=GroqMatchingEvaluator(),
        db=db,
        limit=20
    )

    prefs = db.query(UserPreferences).filter_by(user_id=current_user.id).first()
    app_mode = getattr(prefs, "application_mode", "RECOMMEND_ONLY") or "RECOMMEND_ONLY"

    # Log evaluation action
    ApplicationDecisionService.log_activity(
        current_user.id,
        "EVALUATED_MATCHES",
        f"Evaluated {len(matches_with_jobs)} top opportunities against candidate profile & preferences.",
        None,
        db
    )

    applied_count = 0
    skipped_count = 0
    actions_taken = []

    for match, job in matches_with_jobs:
        eligibility = ApplicationDecisionService.evaluate_eligibility(current_user.id, job.id, db)
        
        if eligibility["already_applied"]:
            continue

        # Phase 2: Use is_auto_eligible instead of eligible
        if eligibility["is_auto_eligible"]:
            # Execute automatic application
            try:
                app = ApplicationService.process_match(
                    match_id=match.id,
                    user_id=current_user.id,
                    application_channel=playwright_channel,
                    db=db
                )
                applied_count += 1
                msg = f"Applied automatically to '{job.title}' at {job.company} (Score: {match.compatibility_score}%)."
                ApplicationDecisionService.log_activity(current_user.id, "AUTO_APPLIED", msg, job.id, db)
                actions_taken.append({"job_title": job.title, "company": job.company, "action": "APPLIED"})
                
                # Phase 2: Execute submission in background
                if app.status == ApplicationStatus.SUBMITTING:
                    background_tasks.add_task(_execute_submission_background, app.id, current_user.id)
                    
            except Exception as err:
                logger.warning(f"Auto apply failed for job {job.id}: {err}")
        elif not eligibility["all_rules_pass"]:
            skipped_count += 1
            reason_msg = eligibility["reasons"][0] if eligibility["reasons"] else "Rules did not pass"
            ApplicationDecisionService.log_activity(
                current_user.id,
                "SKIPPED_OPPORTUNITY",
                f"Skipped '{job.title}' at {job.company}: {reason_msg}.",
                job.id,
                db
            )

    return {
        "status": "COMPLETED",
        "mode": app_mode,
        "evaluated_count": len(matches_with_jobs),
        "applied_count": applied_count,
        "skipped_count": skipped_count,
        "actions": actions_taken
    }


@router.get("/activity")
def get_agent_activity(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves recent activity logs recorded by the AI Recruitment Agent.
    """
    from applications.models import AgentActivityLog
    logs = (
        db.query(AgentActivityLog)
        .filter_by(user_id=current_user.id)
        .order_by(AgentActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "message": log.message,
            "job_offer_id": str(log.job_offer_id) if log.job_offer_id else None,
            "created_at": log.created_at.isoformat()
        }
        for log in logs
    ]

