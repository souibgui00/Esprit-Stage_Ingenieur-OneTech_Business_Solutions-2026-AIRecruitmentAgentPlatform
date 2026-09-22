import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from cv_management.models import CV
from job_sourcing.models import JobOffer, OfferStatus
from matching.models import Match
from matching.matching_service import MatchingService
from matching.adapters.cosine_similarity_calculator import PgVectorSimilarityCalculator
from matching.adapters.groq_matching_evaluator import GroqMatchingEvaluator
from user_management.models import User, UserPreferences
from applications.models import Application, ApplicationStatus, AgentActivityLog

logger = logging.getLogger(__name__)

# Singletons for similarity calculator & evaluator
_similarity_calculator = PgVectorSimilarityCalculator()
_llm_evaluator = GroqMatchingEvaluator()


class ApplicationDecisionService:
    """
    Service responsible for evaluating whether an opportunity is eligible for automatic application
    based on matching score, candidate preferences, duplicate protection, daily limit, and autonomy rules.
    """

    @staticmethod
    def evaluate_eligibility(user_id: uuid.UUID, job_offer_id: uuid.UUID, db: Session) -> Dict[str, Any]:
        """
        Evaluate full eligibility for a job offer.
        Returns a structured dictionary with boolean status, reasons, and individual check breakdowns.
        """
        job_offer = db.get(JobOffer, job_offer_id)
        if not job_offer:
            return {
                "eligible": False,
                "application_mode": "RECOMMEND_ONLY",
                "summary_reason": "Job offer not found.",
                "checks": {}
            }

        # 1. Fetch user preferences
        prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()
        app_mode = getattr(prefs, "application_mode", "RECOMMEND_ONLY") or "RECOMMEND_ONLY"
        min_score = float(getattr(prefs, "min_match_score", 80.0) or 80.0)
        max_daily = int(getattr(prefs, "max_applications_per_day", 5) or 5)
        target_roles = getattr(prefs, "target_roles", []) or []

        # 2. Get user's latest parsed CV
        latest_cv = (
            db.query(CV)
            .filter_by(user_id=user_id, status="PARSED")
            .order_by(CV.created_at.desc())
            .first()
        )

        if not latest_cv:
            return {
                "eligible": False,
                "application_mode": app_mode,
                "summary_reason": "No parsed CV available for evaluation.",
                "checks": {
                    "cv_check": {"passed": False, "message": "Missing parsed CV"}
                }
            }

        # 3. Retrieve or compute Match record
        match = db.query(Match).filter_by(cv_id=latest_cv.id, job_offer_id=job_offer_id).first()
        if not match:
            try:
                match = MatchingService.compute_match(
                    latest_cv.id, job_offer_id, user_id, _similarity_calculator, _llm_evaluator, db
                )
            except Exception as e:
                logger.warning(f"Failed to compute match on-the-fly: {e}")
                return {
                    "eligible": False,
                    "application_mode": app_mode,
                    "summary_reason": "Matching calculation failed.",
                    "checks": {}
                }

        compat_score = match.compatibility_score if match else 0.0

        # --- Rule 1: Compatibility Score Check ---
        score_passed = compat_score >= min_score
        score_msg = f"Match score {compat_score}% ≥ {min_score}% required threshold" if score_passed else f"Match score {compat_score}% is below configured threshold of {min_score}%"

        # --- Rule 2: User Preference Check (Location & Contract) ---
        prefs_passed = MatchingService.passes_user_preferences(job_offer, prefs)
        pref_msg = "Job matches location & contract type preferences" if prefs_passed else "Job location or contract type does not match configured preferences"

        # --- Rule 3: Target Roles Check ---
        role_passed = True
        role_msg = "Job matches target roles"
        if target_roles:
            job_title_lower = job_offer.title.lower()
            role_passed = any(r.lower() in job_title_lower for r in target_roles)
            if not role_passed:
                role_msg = f"Job title does not contain any target role keyword ({', '.join(target_roles)})"

        # --- Rule 4: Duplicate Application Check ---
        # Phase 2: Use job_offer_id directly (Phase 1 constraint)
        existing_app = (
            db.query(Application)
            .filter(Application.user_id == user_id, Application.job_offer_id == job_offer_id)
            .first()
        )
        no_duplicate = existing_app is None
        dup_msg = "No prior application submitted" if no_duplicate else "SKIP_ALREADY_APPLIED: Candidate has already applied to this opportunity"

        # --- Rule 5: Daily Application Limit Check ---
        # Phase 2: Only count SUBMITTING and SENT status applications
        # FAILED, REJECTED, ACTION_REQUIRED do not consume the limit
        # DRAFT and PENDING_VALIDATION do not count as submission attempts
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        apps_today = (
            db.query(func.count(Application.id))
            .filter(
                Application.user_id == user_id,
                Application.created_at >= today_start,
                Application.status.in_([ApplicationStatus.SUBMITTING, ApplicationStatus.SENT])
            )
            .scalar() or 0
        )
        limit_passed = apps_today < max_daily
        limit_msg = f"Daily limit: {apps_today}/{max_daily} applications submitted today" if limit_passed else f"SKIP_DAILY_LIMIT: Configured daily limit of {max_daily} applications reached for today"

        # --- Aggregate Qualification (separate from mode) ---
        all_checks_passed = (
            score_passed and prefs_passed and role_passed and no_duplicate and limit_passed
        )

        reasons = []
        if not score_passed: reasons.append(score_msg)
        if not prefs_passed: reasons.append(pref_msg)
        if not role_passed:  reasons.append(role_msg)
        if not no_duplicate: reasons.append(dup_msg)
        if not limit_passed: reasons.append(limit_msg)

        # --- Determine eligibility based on qualification AND mode ---
        # Phase 2: Eligibility = qualification, mode determines automation
        is_qualified = all_checks_passed
        is_auto_eligible = is_qualified and app_mode == "AUTO_APPLY"

        if is_qualified:
            if app_mode == "AUTO_APPLY":
                summary_reason = "🤖 Qualified for automatic application"
            elif app_mode == "ASSISTED":
                summary_reason = "👤 Qualified — Assisted mode active"
            else:
                summary_reason = "👤 Qualified — Manual mode active"
        else:
            summary_reason = f"Not qualified: {reasons[0]}"

        return {
            "eligible": is_qualified,  # Phase 2: Eligibility = qualification only
            "is_auto_eligible": is_auto_eligible,  # Separate auto-apply eligibility
            "all_rules_pass": all_checks_passed,
            "application_mode": app_mode,
            "compatibility_score": compat_score,
            "min_match_score": min_score,
            "summary_reason": summary_reason,
            "reasons": reasons,
            "already_applied": not no_duplicate,
            "existing_application_id": str(existing_app.id) if existing_app else None,
            "checks": {
                "score_check": {"passed": score_passed, "actual": compat_score, "required": min_score, "message": score_msg},
                "preference_check": {"passed": prefs_passed, "message": pref_msg},
                "target_role_check": {"passed": role_passed, "target_roles": target_roles, "message": role_msg},
                "duplicate_check": {"passed": no_duplicate, "already_applied": not no_duplicate, "message": dup_msg},
                "daily_limit_check": {"passed": limit_passed, "used_today": apps_today, "max_per_day": max_daily, "message": limit_msg},
            }
        }

    @staticmethod
    def log_activity(user_id: uuid.UUID, action: str, message: str, job_offer_id: Optional[uuid.UUID], db: Session):
        """Record an entry in the agent activity log."""
        log_entry = AgentActivityLog(
            user_id=user_id,
            action=action,
            message=message,
            job_offer_id=job_offer_id
        )
        db.add(log_entry)
        db.commit()
