import uuid
import os
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from cv_management.models import CV, PersonalInfo, Experience, CVSkill, Skill
from job_sourcing.models import JobOffer
from matching.models import Match
from matching.matching_service import MatchingService
from applications.models import Application, ApplicationMode, ApplicationStatus
from applications.ports.application_channel import IApplicationChannel
from notifications.models import NotificationType
from notifications.services import NotificationService
from user_management.models import UserPreferences


def _generate_cover_letter(candidate_name: str, job_title: str, company: str, match_summary: str) -> str:
    """
    Generates a professional, personalized cover letter using Groq LLM.
    Phase 3: Extracted from Playwright channel for pre-submission review.
    """
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    groq_model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    
    if not groq_api_key:
        cover_letter = f"""Madame, Monsieur,

Je souhaite poser ma candidature pour le poste de {job_title} chez {company}.
Fort de mon parcours, je serais ravi d'apporter mes compétences à votre équipe.

Cordialement,
{candidate_name}"""
        if not cover_letter or len(cover_letter) < 10:
            cover_letter = f"""Madame, Monsieur,

Je postule au poste de {job_title} chez {company}.

Cordialement,
{candidate_name}"""
        return cover_letter

    try:
        from groq import Groq
        client = Groq(api_key=groq_api_key)
        
        prompt = f"""Rédige une lettre de motivation professionnelle, courtoise et percutante en français (max 200 mots) pour poser ma candidature au poste ci-dessous.

Candidat : {candidate_name}
Poste : {job_title}
Entreprise : {company}
Synthèse de compatibilité : {match_summary}

Ne mets pas d'en-tête de date ni d'adresse. Commence par 'Madame, Monsieur,' et termine par la signature du candidat."""

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Tu es un assistant RH spécialisé dans la rédaction de lettres de motivation percutantes."},
                {"role": "user", "content": prompt}
            ],
            model=groq_model,
            temperature=0.6,
            max_tokens=400,
        )
        cover_letter = response.choices[0].message.content.strip()
        # Ensure non-empty cover letter
        if not cover_letter or len(cover_letter) < 10:
            raise ValueError("Groq returned empty or too short cover letter")
        return cover_letter
    except Exception as e:
        cover_letter = f"""Madame, Monsieur,

Je postule avec enthousiasme au poste de {job_title} chez {company}.
{match_summary}

Cordialement,
{candidate_name}"""
        if not cover_letter or len(cover_letter) < 10:
            cover_letter = f"""Madame, Monsieur,

Je postule au poste de {job_title} chez {company}.

Cordialement,
{candidate_name}"""
        return cover_letter


def _fetch_cv_enrichment(db: Session, cv_id: uuid.UUID):
    """
    Fetches all enrichment data for a CV to build a rich application email:
    - personal_info: PersonalInfo object
    - experiences: list of Experience objects (newest first)
    - skills: list of skill names
    """
    personal_info = db.query(PersonalInfo).filter_by(cv_id=cv_id).first()
    experiences = (
        db.query(Experience)
        .filter_by(cv_id=cv_id)
        .order_by(Experience.start_date.desc())
        .all()
    )
    # Fetch skill names via join
    cv_skills = db.query(CVSkill).filter_by(cv_id=cv_id).all()
    skill_names = []
    for cs in cv_skills:
        skill = db.get(Skill, cs.skill_id)
        if skill:
            skill_names.append(skill.canonical_name)

    return personal_info, experiences, skill_names


class ApplicationService:

    @staticmethod
    def process_match(
        match_id: uuid.UUID,
        user_id: uuid.UUID,
        application_channel: IApplicationChannel,
        db: Session
    ) -> Application:
        # 1. Fetch match and verify existence
        match = db.get(Match, match_id)
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match non trouvé")

        # 2. Security Check: Ownership verification via CV
        cv = db.get(CV, match.cv_id)
        if not cv or cv.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : ce match ne vous appartient pas."
            )

        # 3. Check for duplicates using job_offer_id (Phase 1 constraint)
        job_offer = db.get(JobOffer, match.job_offer_id)
        existing_app = db.query(Application).filter_by(
            user_id=user_id,
            job_offer_id=job_offer.id
        ).first()
        if existing_app:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Une candidature existe déjà pour cette offre d'emploi."
            )

        # 4. Fetch UserPreferences (single source of truth)
        from user_management.models import UserPreferences
        prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()
        if not prefs:
            # Create default preferences if not exist
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            db.flush()

        # 5. Determine mode from UserPreferences
        app_mode_str = getattr(prefs, "application_mode", "RECOMMEND_ONLY") or "RECOMMEND_ONLY"
        
        # Map string to ApplicationMode enum
        mode_mapping = {
            "RECOMMEND_ONLY": ApplicationMode.MANUAL_VALIDATION,
            "MANUAL_VALIDATION": ApplicationMode.MANUAL_VALIDATION,
            "ASSISTED": ApplicationMode.ASSISTED,
            "AUTO_APPLY": ApplicationMode.FULL_AUTO
        }
        mode = mode_mapping.get(app_mode_str, ApplicationMode.MANUAL_VALIDATION)

        # 6. Create Application record with SUBMITTING status for background execution
        initial_status = ApplicationStatus.SUBMITTING if mode == ApplicationMode.FULL_AUTO else ApplicationStatus.PENDING_VALIDATION
        
        application = Application(
            job_offer_id=job_offer.id,
            match_id=match_id,
            user_id=user_id,
            mode=mode,
            status=initial_status
        )
        db.add(application)
        db.flush()  # get UUID assigned

        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def execute_submission(
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        application_channel: IApplicationChannel,
        db: Session
    ) -> Application:
        """
        Execute Playwright submission for an application in background.
        This should be called via FastAPI BackgroundTasks after application creation/approval.
        Phase 3: Sets status to SUBMITTING before execution.
        """
        application = db.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")

        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : cette candidature appartient à un autre utilisateur."
            )

        # Phase 3: Set status to SUBMITTING before execution
        if application.status != ApplicationStatus.SUBMITTING:
            application.status = ApplicationStatus.SUBMITTING
            db.commit()
            db.refresh(application)

        # Phase 2: Use job_offer_id directly, match_id may be NULL
        job_offer = db.get(JobOffer, application.job_offer_id)
        if not job_offer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offre d'emploi non trouvée")

        # Get CV - prefer via match if available, otherwise get latest
        cv = None
        if application.match_id:
            match = db.get(Match, application.match_id)
            if match:
                cv = db.get(CV, match.cv_id)
        
        if not cv:
            # Fallback to latest CV
            cv = db.query(CV).filter_by(user_id=user_id).order_by(CV.created_at.desc()).first()
        
        if not cv:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CV non trouvé")

        # Fetch all enrichment data for rich email
        personal_info, experiences, skill_names = _fetch_cv_enrichment(db, cv.id)
        candidate_email = personal_info.email if personal_info else None
        
        # Get match if available for enrichment
        match = db.get(Match, application.match_id) if application.match_id else None

        result = application_channel.submit(
            application, cv, job_offer,
            candidate_email=candidate_email,
            match=match,
            personal_info=personal_info,
            experiences=experiences,
            skills=skill_names,
            user_responses=application.user_responses
        )
        application.cover_letter = result.get("cover_letter")
        application.execution_logs = result.get("execution_logs")
        application.screenshots = result.get("screenshots")
        
        # Save pending questions if present
        if result.get("pending_questions"):
            application.pending_questions = result.get("pending_questions")

        if result.get("success"):
            status_returned = result.get("status", "SENT")
            if status_returned == "MANUAL_REQUIRED":
                reason = result.get("error_message") or "Intervention humaine requise (CAPTCHA ou Login)"
                application.status = ApplicationStatus.ACTION_REQUIRED
                application.failure_reason = reason
                NotificationService.create_notification(
                    db=db,
                    user_id=user_id,
                    type=NotificationType.ACTION_REQUIRED,
                    message=f"Action requise pour {job_offer.title} chez {job_offer.company} : {reason}.",
                    related_application_id=application.id
                )
            elif status_returned == "ACTION_REQUIRED":
                reason = result.get("error_message") or "Questions en attente de réponse"
                application.status = ApplicationStatus.ACTION_REQUIRED
                application.failure_reason = reason
                NotificationService.create_notification(
                    db=db,
                    user_id=user_id,
                    type=NotificationType.ACTION_REQUIRED,
                    message=f"Questions en attente pour {job_offer.title} chez {job_offer.company} : {reason}.",
                    related_application_id=application.id
                )
            else:
                application.status = ApplicationStatus.SENT
                application.submitted_at = datetime.utcnow()
                application.failure_reason = None
                NotificationService.create_notification(
                    db=db,
                    user_id=user_id,
                    type=NotificationType.APPLICATION_SENT,
                    message=f"Candidature traitée avec succès pour {job_offer.title} chez {job_offer.company}.",
                    related_application_id=application.id
                )
        else:
            reason = result.get("error_message") or "Erreur d'exécution de l'agent web"
            application.status = ApplicationStatus.FAILED
            application.failure_reason = reason
            NotificationService.create_notification(
                db=db,
                user_id=user_id,
                type=NotificationType.APPLICATION_FAILED,
                message=f"Échec de l'envoi pour {job_offer.title} chez {job_offer.company} : {reason}.",
                related_application_id=application.id
            )

        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def approve_application(
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session
    ) -> Application:
        """
        Approve an application for submission.
        Phase 3: No longer executes Playwright synchronously.
        Returns application with APPROVED status for background submission.
        """
        # 1. Fetch application
        application = db.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")

        # 2. Check ownership
        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : cette candidature appartient à un autre utilisateur."
            )

        # 3. Check transition (only allow from PENDING_VALIDATION)
        if application.status != ApplicationStatus.PENDING_VALIDATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Impossible d'approuver une candidature dans l'état : {application.status}."
            )

        # 4. Verify duplicate protection (check if already submitted via job_offer_id)
        existing_sent = (
            db.query(Application)
            .filter(
                Application.user_id == user_id,
                Application.job_offer_id == application.job_offer_id,
                Application.status.in_([ApplicationStatus.SENT, ApplicationStatus.SUBMITTING])
            )
            .first()
        )
        if existing_sent and existing_sent.id != application.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Une candidature est déjà en cours ou a déjà été soumise pour cette offre."
            )

        # 5. State transition to APPROVED
        application.approve()
        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def run_agent(
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        application_channel: IApplicationChannel,
        db: Session
    ) -> Application:
        application = db.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")

        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : cette candidature appartient à un autre utilisateur."
            )

        # Phase 2: Use job_offer_id directly
        job_offer = db.get(JobOffer, application.job_offer_id)
        if not job_offer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offre d'emploi non trouvée")

        # Get CV - prefer via match if available, otherwise get latest
        cv = None
        if application.match_id:
            match = db.get(Match, application.match_id)
            if match:
                cv = db.get(CV, match.cv_id)
        
        if not cv:
            cv = db.query(CV).filter_by(user_id=user_id).order_by(CV.created_at.desc()).first()
        
        if not cv:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CV non trouvé")

        personal_info, experiences, skill_names = _fetch_cv_enrichment(db, cv.id)
        candidate_email = personal_info.email if personal_info else None

        # Get match if available for enrichment
        match = db.get(Match, application.match_id) if application.match_id else None

        result = application_channel.submit(
            application, cv, job_offer,
            candidate_email=candidate_email,
            match=match,
            personal_info=personal_info,
            experiences=experiences,
            skills=skill_names,
            user_responses=application.user_responses
        )

        application.cover_letter = result.get("cover_letter")
        application.execution_logs = result.get("execution_logs")
        application.screenshots = result.get("screenshots")
        
        # Save pending questions if present
        if result.get("pending_questions"):
            application.pending_questions = result.get("pending_questions")

        if result.get("success"):
            status_returned = result.get("status", "SENT")
            if status_returned == "MANUAL_REQUIRED":
                reason = result.get("error_message") or "Intervention humaine requise"
                application.status = ApplicationStatus.ACTION_REQUIRED
                application.failure_reason = reason
            elif status_returned == "ACTION_REQUIRED":
                reason = result.get("error_message") or "Questions en attente de réponse"
                application.status = ApplicationStatus.ACTION_REQUIRED
                application.failure_reason = reason
            else:
                application.status = ApplicationStatus.SENT
                application.submitted_at = datetime.utcnow()
                application.failure_reason = None
        else:
            reason = result.get("error_message") or "Erreur d'exécution de l'agent web"
            application.status = ApplicationStatus.FAILED
            application.failure_reason = reason

        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def reject_application(
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: Optional[str],
        db: Session
    ) -> Application:
        # 1. Fetch application
        application = db.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")

        # 2. Check ownership
        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : cette candidature appartient à un autre utilisateur."
            )

        # 3. Check transition
        if application.status != ApplicationStatus.PENDING_VALIDATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Impossible de rejeter une candidature dans l'état : {application.status}."
            )

        # 4. Reject
        application.reject(reason)
        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def generate_cover_letter_for_application(
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session
    ) -> Application:
        """
        Generate a cover letter for an application without triggering submission.
        Phase 3: Allows cover letter review before approval in Assisted mode.
        """
        # 1. Fetch application
        application = db.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")

        # 2. Check ownership
        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : cette candidature appartient à un autre utilisateur."
            )

        # 3. Check if cover letter can be generated (only for not-submitted applications)
        if application.status in [ApplicationStatus.SENT, ApplicationStatus.SUBMITTING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de générer une lettre de motivation pour une candidature déjà soumise."
            )

        # 4. Get job offer
        job_offer = db.get(JobOffer, application.job_offer_id)
        if not job_offer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offre d'emploi non trouvée")

        # 5. Get match if available for summary
        match_summary = "Profil compatible avec le poste."
        if application.match_id:
            match = db.get(Match, application.match_id)
            if match and match.summary:
                match_summary = match.summary

        # 6. Get candidate name
        candidate_name = "Candidat"
        cv = None
        if application.match_id:
            match = db.get(Match, application.match_id)
            if match:
                cv = db.get(CV, match.cv_id)
        
        if not cv:
            cv = db.query(CV).filter_by(user_id=user_id).order_by(CV.created_at.desc()).first()
        
        if cv:
            personal_info = db.query(PersonalInfo).filter_by(cv_id=cv.id).first()
            if personal_info and personal_info.full_name:
                candidate_name = personal_info.full_name

        # 7. Generate cover letter
        cover_letter = _generate_cover_letter(candidate_name, job_offer.title, job_offer.company, match_summary)
        
        # Ensure cover letter is not empty
        if not cover_letter or len(cover_letter) < 10:
            cover_letter = f"""Madame, Monsieur,

Je souhaite poser ma candidature pour le poste de {job_offer.title} chez {job_offer.company}.
Fort de mon parcours, je serais ravi d'apporter mes compétences à votre équipe.

Cordialement,
{candidate_name}"""

        # 8. Update application
        application.cover_letter = cover_letter
        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def update_cover_letter(
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        cover_letter_content: str,
        db: Session
    ) -> Application:
        """
        Update the cover letter for an application.
        Phase 3: Allows manual editing before submission.
        """
        # 1. Fetch application
        application = db.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")

        # 2. Check ownership
        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : cette candidature appartient à un autre utilisateur."
            )

        # 3. Check if cover letter can be updated
        allowed_statuses = [
            ApplicationStatus.DRAFT,
            ApplicationStatus.PENDING_VALIDATION,
            ApplicationStatus.APPROVED,
            ApplicationStatus.ACTION_REQUIRED
        ]
        if application.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Impossible de modifier la lettre de motivation pour une candidature dans l'état : {application.status}."
            )

        # 4. Update cover letter
        application.cover_letter = cover_letter_content
        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def get_applications(
        db: Session,
        user_id: uuid.UUID,
        status_filter: Optional[ApplicationStatus] = None
    ) -> List[Application]:
        query = db.query(Application).filter_by(user_id=user_id)
        if status_filter:
            query = query.filter_by(status=status_filter)
        return query.order_by(Application.created_at.desc()).all()

    @staticmethod
    def answer_questions(
        application_id: uuid.UUID,
        user_id: uuid.UUID,
        answers: Dict[str, str],
        application_channel: IApplicationChannel,
        db: Session
    ) -> Application:
        """
        Accept user answers for pending questions and resume the application process.
        """
        # 1. Fetch application
        application = db.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidature non trouvée")

        # 2. Check ownership
        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : cette candidature appartient à un autre utilisateur."
            )

        # 3. Check if application is in ACTION_REQUIRED or SUBMITTING status
        if application.status not in (ApplicationStatus.ACTION_REQUIRED, ApplicationStatus.SUBMITTING):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cette candidature n'est pas en attente de réponses."
            )


        # 4. Save user responses and update status to SUBMITTING
        application.user_responses = answers
        application.status = ApplicationStatus.SUBMITTING
        db.commit()
        db.refresh(application)
        return application

