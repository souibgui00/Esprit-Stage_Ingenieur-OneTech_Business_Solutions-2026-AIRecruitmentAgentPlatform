import pytest
import uuid
from datetime import datetime
from applications.decision_service import ApplicationDecisionService
from applications.models import Application, ApplicationStatus, ApplicationMode
from user_management.models import User, UserPreferences
from job_sourcing.models import JobOffer, JobSource, ContractType, OfferStatus
from cv_management.models import CV
from matching.models import Match
from shared.database import SessionLocal

def test_decision_service_unit():
    db = SessionLocal()
    try:
        # Setup mock user and preferences
        user = User(email=f"test_decision_{uuid.uuid4()}@example.com", hashed_password="pw")
        db.add(user)
        db.commit()

        prefs = UserPreferences(
            user_id=user.id,
            job_keywords="python react",
            preferred_locations=["France"],
            preferred_contract_types=["STAGE"],
            application_mode="AUTO_APPLY",
            min_match_score=80.0,
            max_applications_per_day=5
        )
        db.add(prefs)

        # Setup job source & offer
        from job_sourcing.models import SourceType
        src = JobSource(name="Test Source", type=SourceType.OFFICIAL_API, base_url="http://example.com")
        db.add(src)
        db.commit()

        job = JobOffer(
            source_id=src.id,
            source_url=f"http://example.com/{uuid.uuid4()}",
            fingerprint=str(uuid.uuid4()),
            title="Software Engineer Intern",
            company="TechCorp",
            location="Paris, France",
            description="Stage Software Engineer Python React",
            contract_type=ContractType.STAGE,
            status=OfferStatus.NEW
        )
        db.add(job)

        # Setup parsed CV
        from cv_management.models import CVStatus
        cv = CV(user_id=user.id, filename="test.pdf", raw_file_url="http://test.com", language="fr", status=CVStatus.PARSED)
        db.add(cv)
        db.commit()

        # Create high match score (85%)
        match = Match(
            cv_id=cv.id,
            job_offer_id=job.id,
            semantic_similarity=0.8,
            llm_score=8.5,
            compatibility_score=85.0,
            skills_score=30.0,
            experience_score=15.0,
            seniority_score=10.0,
            semantic_score=12.0,
            certification_bonus=0.0,
            matching_points=["Good Python skills"],
            gap_points=[]
        )
        db.add(match)
        db.commit()

        # Test 1: High match score, matching preferences, AUTO_APPLY -> Eligible
        res = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        assert res["eligible"] is True  # Phase 2: eligible = qualification
        assert res["is_auto_eligible"] is True  # Auto-apply eligible
        assert res["all_rules_pass"] is True
        assert res["already_applied"] is False

        # Test 2: Mode changed to RECOMMEND_ONLY -> Not auto-apply eligible, but still qualified
        prefs.application_mode = "RECOMMEND_ONLY"
        db.commit()

        res2 = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        assert res2["eligible"] is True  # Still qualified
        assert res2["is_auto_eligible"] is False  # Not auto-eligible
        assert "RECOMMEND_ONLY" in res2["application_mode"]

        # Test 3: Duplicate protection check
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()

        res3 = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        assert res3["already_applied"] is True
        assert res3["all_rules_pass"] is False
        assert "SKIP_ALREADY_APPLIED" in res3["summary_reason"]
    finally:
        db.close()
