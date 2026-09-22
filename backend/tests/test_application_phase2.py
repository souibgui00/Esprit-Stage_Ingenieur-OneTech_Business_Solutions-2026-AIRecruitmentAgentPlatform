"""
Phase 2 Application Management Tests: Service & Preference Unification + Background Submission.

Covers:
1. UserPreferences as single source of truth for application eligibility.
2. Eligibility semantics: qualification vs mode separation.
3. Daily application limit: only SUBMITTING and SENT count.
4. FAILED, REJECTED, ACTION_REQUIRED do not consume limit.
5. DRAFT/PENDING_VALIDATION do not consume submission limit.
6. Background submission instead of synchronous Playwright.
7. Status transitions: SUBMITTING → SENT/FAILED/ACTION_REQUIRED.
8. Obsolete MatchingConfig/UserAutoApplySettings are not used.
9. Application uses job_offer_id directly (match_id may be NULL).
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.exc import IntegrityError

from shared.database import SessionLocal
from user_management.models import User, UserPreferences
from job_sourcing.models import JobOffer, JobSource, SourceType, ContractType, OfferStatus
from cv_management.models import CV, CVStatus
from matching.models import Match
from applications.models import Application, ApplicationMode, ApplicationStatus
from applications.application_service import ApplicationService
from applications.decision_service import ApplicationDecisionService
from applications.ports.application_channel import IApplicationChannel


@pytest.fixture(autouse=True)
def cleanup_test_records():
    """Cleanup only test records created with test_phase2_ prefix."""
    yield
    db = SessionLocal()
    try:
        # Delete test applications first
        test_apps = (
            db.query(Application)
            .join(User, Application.user_id == User.id)
            .filter(User.email.ilike("test_phase2_%"))
            .all()
        )
        for app in test_apps:
            db.delete(app)
        db.commit()

        # Delete test matches
        test_matches = (
            db.query(Match)
            .join(CV, Match.cv_id == CV.id)
            .join(User, CV.user_id == User.id)
            .filter(User.email.ilike("test_phase2_%"))
            .all()
        )
        for m in test_matches:
            db.delete(m)
        db.commit()

        # Delete test CVs
        test_cvs = (
            db.query(CV)
            .join(User, CV.user_id == User.id)
            .filter(User.email.ilike("test_phase2_%"))
            .all()
        )
        for c in test_cvs:
            db.delete(c)
        db.commit()

        # Delete test job offers
        test_jobs = db.query(JobOffer).filter(JobOffer.fingerprint.ilike("test_phase2_%")).all()
        for j in test_jobs:
            db.delete(j)
        db.commit()

        # Delete test job sources
        test_sources = db.query(JobSource).filter(JobSource.name.ilike("test_phase2_%")).all()
        for s in test_sources:
            db.delete(s)
        db.commit()

        # Delete test preferences
        test_prefs = (
            db.query(UserPreferences)
            .join(User, UserPreferences.user_id == User.id)
            .filter(User.email.ilike("test_phase2_%"))
            .all()
        )
        for p in test_prefs:
            db.delete(p)
        db.commit()

        # Delete test users
        test_users = db.query(User).filter(User.email.ilike("test_phase2_%")).all()
        for u in test_users:
            db.delete(u)
        db.commit()
    finally:
        db.close()


def _create_test_source(db):
    source = JobSource(
        name=f"test_phase2_src_{uuid.uuid4().hex[:8]}",
        type=SourceType.OFFICIAL_API,
        base_url="https://example.com"
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _create_test_job(db, source_id):
    job = JobOffer(
        source_id=source_id,
        source_url=f"https://example.com/{uuid.uuid4()}",
        fingerprint=f"test_phase2_job_{uuid.uuid4()}",
        title="Software Engineer",
        company="TechCorp",
        location="Paris, France",
        description="Software engineer role",
        contract_type=ContractType.CDI,
        status=OfferStatus.NEW
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _create_test_user(db):
    user = User(
        email=f"test_phase2_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hashed_pw_test"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_test_cv_and_match(db, user, job):
    cv = CV(
        user_id=user.id,
        filename="cv.pdf",
        raw_file_url="uploaded_cvs/test.pdf",
        language="fr",
        status=CVStatus.PARSED
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)

    match = Match(
        cv_id=cv.id,
        job_offer_id=job.id,
        compatibility_score=85.0,
        skills_score=30.0,
        experience_score=18.0,
        seniority_score=10.0,
        semantic_score=13.0,
        certification_bonus=4.0,
        semantic_similarity=0.82
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return cv, match


# ─────────────────────────────────────────────────────────────
# 1. UserPreferences as single source of truth
# ─────────────────────────────────────────────────────────────
def test_userpreferences_min_match_score_respected():
    """Test that UserPreferences.min_match_score is respected."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set min_match_score to 90
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=90.0,
            application_mode="AUTO_APPLY",
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        # Match score is 85, below threshold
        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        assert eligibility["eligible"] is False
        assert eligibility["is_auto_eligible"] is False
        assert eligibility["checks"]["score_check"]["passed"] is False
        assert "below configured threshold" in eligibility["checks"]["score_check"]["message"]
    finally:
        db.close()


def test_userpreferences_target_role_respected():
    """Test that UserPreferences.target_roles is respected."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Data Scientist",
            company="TechCorp",
            location="Paris, France",
            description="Data scientist role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        _, match = _create_test_cv_and_match(db, user, job)

        # Set target role to "Software Engineer"
        prefs = UserPreferences(
            user_id=user.id,
            target_roles=["Software Engineer"],
            min_match_score=70.0,
            application_mode="AUTO_APPLY",
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        # Job title is "Data Scientist", doesn't match target role
        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        assert eligibility["eligible"] is False
        assert eligibility["checks"]["target_role_check"]["passed"] is False
        assert "does not contain any target role" in eligibility["checks"]["target_role_check"]["message"]
    finally:
        db.close()


def test_userpreferences_location_respected():
    """Test that UserPreferences.preferred_locations is respected."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Software Engineer",
            company="TechCorp",
            location="Berlin, Germany",
            description="Software engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        _, match = _create_test_cv_and_match(db, user, job)

        # Set preferred location to "France"
        prefs = UserPreferences(
            user_id=user.id,
            preferred_locations=["France"],
            min_match_score=70.0,
            application_mode="AUTO_APPLY",
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        # Job location is "Berlin, Germany", doesn't match preferred location
        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        assert eligibility["eligible"] is False
        assert eligibility["checks"]["preference_check"]["passed"] is False
    finally:
        db.close()


def test_userpreferences_contract_respected():
    """Test that UserPreferences.preferred_contract_types is respected."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Software Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Software engineer role",
            contract_type=ContractType.CDD,
            status=OfferStatus.NEW
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        _, match = _create_test_cv_and_match(db, user, job)

        # Set preferred contract to "CDI"
        prefs = UserPreferences(
            user_id=user.id,
            preferred_contract_types=["CDI"],
            min_match_score=70.0,
            application_mode="AUTO_APPLY",
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        # Job contract is CDD, doesn't match preferred contract
        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        assert eligibility["eligible"] is False
        assert eligibility["checks"]["preference_check"]["passed"] is False
    finally:
        db.close()


def test_userpreferences_remote_respected():
    """Test that UserPreferences.remote_preference is respected."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Software Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Software engineer role (onsite)",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        _, match = _create_test_cv_and_match(db, user, job)

        # Set remote preference to True (remote only)
        prefs = UserPreferences(
            user_id=user.id,
            remote_preference=True,
            min_match_score=70.0,
            application_mode="AUTO_APPLY",
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        # Job location is "Paris, France" (onsite), doesn't match remote preference
        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        assert eligibility["eligible"] is False
        assert eligibility["checks"]["preference_check"]["passed"] is False
    finally:
        db.close()


def test_userpreferences_application_mode_respected():
    """Test that UserPreferences.application_mode controls automation."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set mode to MANUAL_VALIDATION
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="MANUAL_VALIDATION",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        # Should be qualified but not auto-eligible
        assert eligibility["eligible"] is True  # Phase 2: eligible = qualification
        assert eligibility["is_auto_eligible"] is False
        assert eligibility["application_mode"] == "MANUAL_VALIDATION"
        assert "Manual mode active" in eligibility["summary_reason"]
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 2. Eligibility semantics: qualification vs mode separation
# ─────────────────────────────────────────────────────────────
def test_qualification_separate_from_mode():
    """Test that qualification is separate from application mode."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # High score, MANUAL mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="MANUAL_VALIDATION",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        # Should be qualified (eligible=True) but not auto-eligible
        assert eligibility["eligible"] is True
        assert eligibility["is_auto_eligible"] is False
        assert eligibility["all_rules_pass"] is True
        assert "Qualified — Manual mode active" in eligibility["summary_reason"]
    finally:
        db.close()


def test_assisted_mode_qualification():
    """Test that ASSISTED mode works correctly for qualification."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # High score, ASSISTED mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="ASSISTED",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        # Should be qualified but not auto-eligible (ASSISTED != AUTO_APPLY)
        assert eligibility["eligible"] is True
        assert eligibility["is_auto_eligible"] is False
        assert eligibility["application_mode"] == "ASSISTED"
        assert "Assisted mode active" in eligibility["summary_reason"]
    finally:
        db.close()


def test_auto_apply_mode_auto_eligible():
    """Test that AUTO_APPLY mode with high score is auto-eligible."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # High score, AUTO_APPLY mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="AUTO_APPLY",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        # Should be both qualified and auto-eligible
        assert eligibility["eligible"] is True
        assert eligibility["is_auto_eligible"] is True
        assert eligibility["application_mode"] == "AUTO_APPLY"
        assert "Qualified for automatic application" in eligibility["summary_reason"]
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 3. Daily application limit: only SUBMITTING and SENT count
# ─────────────────────────────────────────────────────────────
def test_daily_limit_counts_submitting_and_sent():
    """Test that only SUBMITTING and SENT count toward daily limit."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        job2 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Backend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Backend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)
        
        _, match1 = _create_test_cv_and_match(db, user, job1)
        _, match2 = _create_test_cv_and_match(db, user, job2)

        # Set max daily limit to 2
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=70.0,
            max_applications_per_day=2
        )
        db.add(prefs)
        db.commit()

        # Create 1 SENT application
        app1 = Application(
            job_offer_id=job1.id,
            match_id=match1.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SENT,
            submitted_at=datetime.utcnow()
        )
        db.add(app1)
        db.commit()

        # Create 1 FAILED application (should not count)
        app2 = Application(
            job_offer_id=job2.id,
            match_id=match2.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.FAILED,
            failure_reason="Test failure"
        )
        db.add(app2)
        db.commit()

        # Check eligibility for new job
        job3 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Frontend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Frontend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job3)
        db.commit()
        db.refresh(job3)
        
        _, match3 = _create_test_cv_and_match(db, user, job3)

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job3.id, db)
        
        # Should have 1 used (only SENT counts, FAILED doesn't)
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 1
        assert eligibility["checks"]["daily_limit_check"]["passed"] is True
    finally:
        db.close()


def test_daily_limit_rejected_does_not_count():
    """Test that REJECTED applications do not consume the limit."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        job2 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Backend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Backend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)
        
        _, match1 = _create_test_cv_and_match(db, user, job1)
        _, match2 = _create_test_cv_and_match(db, user, job2)

        # Set max daily limit to 2
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=70.0,
            max_applications_per_day=2
        )
        db.add(prefs)
        db.commit()

        # Create 1 REJECTED application
        app1 = Application(
            job_offer_id=job1.id,
            match_id=match1.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.REJECTED,
            failure_reason="User rejected"
        )
        db.add(app1)
        db.commit()

        # Check eligibility for new job
        job3 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Frontend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Frontend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job3)
        db.commit()
        db.refresh(job3)
        
        _, match3 = _create_test_cv_and_match(db, user, job3)

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job3.id, db)
        
        # Should have 0 used (REJECTED doesn't count)
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 0
        assert eligibility["checks"]["daily_limit_check"]["passed"] is True
    finally:
        db.close()


def test_daily_limit_action_required_does_not_count():
    """Test that ACTION_REQUIRED applications do not consume the limit."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        job2 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Backend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Backend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)
        
        _, match1 = _create_test_cv_and_match(db, user, job1)
        _, match2 = _create_test_cv_and_match(db, user, job2)

        # Set max daily limit to 2
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=70.0,
            max_applications_per_day=2
        )
        db.add(prefs)
        db.commit()

        # Create 1 ACTION_REQUIRED application
        app1 = Application(
            job_offer_id=job1.id,
            match_id=match1.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.ACTION_REQUIRED,
            failure_reason="CAPTCHA required"
        )
        db.add(app1)
        db.commit()

        # Check eligibility for new job
        job3 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Frontend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Frontend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job3)
        db.commit()
        db.refresh(job3)
        
        _, match3 = _create_test_cv_and_match(db, user, job3)

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job3.id, db)
        
        # Should have 0 used (ACTION_REQUIRED doesn't count)
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 0
        assert eligibility["checks"]["daily_limit_check"]["passed"] is True
    finally:
        db.close()


def test_daily_limit_draft_does_not_count():
    """Test that DRAFT applications do not consume the submission limit."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        job2 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Backend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Backend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)
        
        _, match1 = _create_test_cv_and_match(db, user, job1)
        _, match2 = _create_test_cv_and_match(db, user, job2)

        # Set max daily limit to 2
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=70.0,
            max_applications_per_day=2
        )
        db.add(prefs)
        db.commit()

        # Create 1 DRAFT application
        app1 = Application(
            job_offer_id=job1.id,
            match_id=match1.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.DRAFT
        )
        db.add(app1)
        db.commit()

        # Check eligibility for new job
        job3 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Frontend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Frontend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job3)
        db.commit()
        db.refresh(job3)
        
        _, match3 = _create_test_cv_and_match(db, user, job3)

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job3.id, db)
        
        # Should have 0 used (DRAFT doesn't count)
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 0
        assert eligibility["checks"]["daily_limit_check"]["passed"] is True
    finally:
        db.close()


def test_daily_limit_pending_validation_does_not_count():
    """Test that PENDING_VALIDATION applications do not consume the submission limit."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        job2 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Backend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Backend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)
        
        _, match1 = _create_test_cv_and_match(db, user, job1)
        _, match2 = _create_test_cv_and_match(db, user, job2)

        # Set max daily limit to 2
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=70.0,
            max_applications_per_day=2
        )
        db.add(prefs)
        db.commit()

        # Create 1 PENDING_VALIDATION application
        app1 = Application(
            job_offer_id=job1.id,
            match_id=match1.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app1)
        db.commit()

        # Check eligibility for new job
        job3 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Frontend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Frontend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job3)
        db.commit()
        db.refresh(job3)
        
        _, match3 = _create_test_cv_and_match(db, user, job3)

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job3.id, db)
        
        # Should have 0 used (PENDING_VALIDATION doesn't count)
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 0
        assert eligibility["checks"]["daily_limit_check"]["passed"] is True
    finally:
        db.close()


def test_daily_limit_submitting_counts():
    """Test that SUBMITTING applications count toward the limit."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        job2 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Backend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Backend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)
        
        _, match1 = _create_test_cv_and_match(db, user, job1)
        _, match2 = _create_test_cv_and_match(db, user, job2)

        # Set max daily limit to 1
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=70.0,
            max_applications_per_day=1
        )
        db.add(prefs)
        db.commit()

        # Create 1 SUBMITTING application
        app1 = Application(
            job_offer_id=job1.id,
            match_id=match1.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SUBMITTING
        )
        db.add(app1)
        db.commit()

        # Check eligibility for new job
        job3 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Frontend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Frontend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job3)
        db.commit()
        db.refresh(job3)
        
        _, match3 = _create_test_cv_and_match(db, user, job3)

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job3.id, db)
        
        # Should have 1 used (SUBMITTING counts)
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 1
        assert eligibility["checks"]["daily_limit_check"]["passed"] is False
        assert "limit" in eligibility["checks"]["daily_limit_check"]["message"].lower()
    finally:
        db.close()


def test_daily_limit_sent_counts():
    """Test that SENT applications count toward the limit."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        job2 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Backend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Backend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)
        
        _, match1 = _create_test_cv_and_match(db, user, job1)
        _, match2 = _create_test_cv_and_match(db, user, job2)

        # Set max daily limit to 1
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=70.0,
            max_applications_per_day=1
        )
        db.add(prefs)
        db.commit()

        # Create 1 SENT application
        app1 = Application(
            job_offer_id=job1.id,
            match_id=match1.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SENT,
            submitted_at=datetime.utcnow()
        )
        db.add(app1)
        db.commit()

        # Check eligibility for new job
        job3 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Frontend Engineer",
            company="TechCorp",
            location="Paris, France",
            description="Frontend engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job3)
        db.commit()
        db.refresh(job3)
        
        _, match3 = _create_test_cv_and_match(db, user, job3)

        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job3.id, db)
        
        # Should have 1 used (SENT counts)
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 1
        assert eligibility["checks"]["daily_limit_check"]["passed"] is False
        assert "limit" in eligibility["checks"]["daily_limit_check"]["message"].lower()
    finally:
        db.close()


def test_daily_limit_different_users_independent():
    """Test that different users have independent daily limits."""
    db = SessionLocal()
    try:
        user1 = _create_test_user(db)
        user2 = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        
        _, match1 = _create_test_cv_and_match(db, user1, job)
        _, match2 = _create_test_cv_and_match(db, user2, job)

        # Set max daily limit to 1 for both users
        prefs1 = UserPreferences(
            user_id=user1.id,
            min_match_score=70.0,
            max_applications_per_day=1
        )
        db.add(prefs1)
        
        prefs2 = UserPreferences(
            user_id=user2.id,
            min_match_score=70.0,
            max_applications_per_day=1
        )
        db.add(prefs2)
        db.commit()

        # User1 creates 1 SENT application
        app1 = Application(
            job_offer_id=job.id,
            match_id=match1.id,
            user_id=user1.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SENT,
            submitted_at=datetime.utcnow()
        )
        db.add(app1)
        db.commit()

        # User2 should still be able to apply (independent limit)
        eligibility = ApplicationDecisionService.evaluate_eligibility(user2.id, job.id, db)
        
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 0
        assert eligibility["checks"]["daily_limit_check"]["passed"] is True
    finally:
        db.close()


def test_daily_limit_different_days_reset():
    """Test that daily limit resets correctly for different days."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set max daily limit to 1
        prefs = UserPreferences(
            user_id=user.id,
            min_match_score=70.0,
            max_applications_per_day=1
        )
        db.add(prefs)
        db.commit()

        # Create 1 SENT application from yesterday
        yesterday = datetime.utcnow() - timedelta(days=1)
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SENT,
            submitted_at=yesterday,
            created_at=yesterday
        )
        db.add(app)
        db.commit()

        # Should be able to apply today (limit reset)
        eligibility = ApplicationDecisionService.evaluate_eligibility(user.id, job.id, db)
        
        assert eligibility["checks"]["daily_limit_check"]["used_today"] == 0
        assert eligibility["checks"]["daily_limit_check"]["passed"] is True
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 4. Background submission (mocked)
# ─────────────────────────────────────────────────────────────
def test_background_submission_mock():
    """Test that submission is moved to background with mocked channel."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set AUTO_APPLY mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="AUTO_APPLY",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        # Mock the application channel
        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "SENT",
            "cover_letter": "Test cover letter",
            "execution_logs": {},
            "screenshots": {}
        }

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Phase 2: Should create with SUBMITTING status for AUTO mode
        assert app.status == ApplicationStatus.SUBMITTING
        assert app.mode == ApplicationMode.FULL_AUTO
        assert app.job_offer_id == job.id
        assert app.match_id == match.id

        # Verify channel was NOT called during process_match (moved to background)
        mock_channel.submit.assert_not_called()

        # Execute submission (simulating background task)
        updated_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Should transition to SENT
        assert updated_app.status == ApplicationStatus.SENT
        assert updated_app.submitted_at is not None
        assert updated_app.cover_letter == "Test cover letter"
        assert updated_app.failure_reason is None
    finally:
        db.close()


def test_manual_mode_no_background_submission():
    """Test that MANUAL mode does not trigger background submission."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set MANUAL mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="MANUAL_VALIDATION",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        # Mock the application channel
        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Phase 2: Should create with PENDING_VALIDATION status for MANUAL mode
        assert app.status == ApplicationStatus.PENDING_VALIDATION
        assert app.mode == ApplicationMode.MANUAL_VALIDATION
        assert app.job_offer_id == job.id
        assert app.match_id == match.id

        # Verify channel was not called (no submission for MANUAL mode)
        mock_channel.submit.assert_not_called()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 5. Status transitions
# ─────────────────────────────────────────────────────────────
def test_status_transition_submitting_to_sent():
    """Test SUBMITTING → SENT transition."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "SENT"
        }

        # Create SUBMITTING application
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SUBMITTING
        )
        db.add(app)
        db.commit()

        # Execute submission
        updated_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        assert updated_app.status == ApplicationStatus.SENT
        assert updated_app.submitted_at is not None
    finally:
        db.close()


def test_status_transition_submitting_to_failed():
    """Test SUBMITTING → FAILED transition."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": False,
            "error_message": "Connection timeout"
        }

        # Create SUBMITTING application
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SUBMITTING
        )
        db.add(app)
        db.commit()

        # Execute submission
        updated_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        assert updated_app.status == ApplicationStatus.FAILED
        assert updated_app.failure_reason == "Connection timeout"
    finally:
        db.close()


def test_status_transition_submitting_to_action_required():
    """Test SUBMITTING → ACTION_REQUIRED transition for CAPTCHA."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "MANUAL_REQUIRED",
            "error_message": "CAPTCHA detected"
        }

        # Create SUBMITTING application
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SUBMITTING
        )
        db.add(app)
        db.commit()

        # Execute submission
        updated_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        assert updated_app.status == ApplicationStatus.ACTION_REQUIRED
        assert updated_app.failure_reason == "CAPTCHA detected"
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 6. Application uses job_offer_id directly
# ─────────────────────────────────────────────────────────────
def test_application_uses_job_offer_id():
    """Test that Application uses job_offer_id directly (match_id may be NULL)."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Create application with match_id initially
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()
        db.refresh(app)

        assert app.job_offer_id == job.id
        assert app.match_id == match.id

        # Simulate match deletion (match_id becomes NULL)
        db.delete(match)
        db.commit()

        # Refresh application
        db.refresh(app)

        # job_offer_id should still be intact
        assert app.job_offer_id == job.id
        assert app.match_id is None
    finally:
        db.close()


def test_application_can_exist_without_match():
    """Test that Application can exist with match_id = NULL."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        cv = CV(
            user_id=user.id,
            filename="cv.pdf",
            raw_file_url="uploaded_cvs/test.pdf",
            language="fr",
            status=CVStatus.PARSED
        )
        db.add(cv)
        db.commit()

        # Create application without match_id
        app = Application(
            job_offer_id=job.id,
            match_id=None,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()
        db.refresh(app)

        assert app.job_offer_id == job.id
        assert app.match_id is None
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 7. Duplicate protection via job_offer_id
# ─────────────────────────────────────────────────────────────
def test_duplicate_protection_via_job_offer_id():
    """Test that duplicate protection works via (user_id, job_offer_id)."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        _, match1 = _create_test_cv_and_match(db, user, job1)

        # Create first application
        app1 = Application(
            job_offer_id=job1.id,
            match_id=match1.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app1)
        db.commit()

        # Try to create second application for same user and same job (should fail)
        # Use a different match_id to avoid hitting the old uq_application_match constraint
        # The new constraint should still catch this because user_id and job_offer_id are the same
        app2 = Application(
            job_offer_id=job1.id,
            match_id=None,  # Use NULL match_id to avoid old constraint
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app2)
        
        with pytest.raises(IntegrityError) as exc_info:
            db.commit()

        db.rollback()
        # Check for the new constraint violation
        assert "uq_user_job_application" in str(exc_info.value).lower() or "unique constraint" in str(exc_info.value).lower()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 8. Run existing Phase 1 tests to ensure no regression
# ─────────────────────────────────────────────────────────────
def test_phase1_regression_duplicate_protection():
    """Ensure Phase 1 duplicate protection still works."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)

        app1 = Application(
            job_offer_id=job.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app1)
        db.commit()

        app2 = Application(
            job_offer_id=job.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.APPROVED
        )
        db.add(app2)
        
        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()
    finally:
        db.close()


def test_phase1_regression_match_deletion_set_null():
    """Ensure Phase 1 match deletion SET NULL still works."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SENT
        )
        db.add(app)
        db.commit()
        app_id = app.id

        # Delete match
        db.delete(match)
        db.commit()

        # Application should still exist with match_id = NULL
        surviving_app = db.get(Application, app_id)
        assert surviving_app is not None
        assert surviving_app.job_offer_id == job.id
        assert surviving_app.match_id is None
    finally:
        db.close()


def test_phase1_regression_enum_values():
    """Ensure Phase 1 enum values still work."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        
        # Create different jobs for each test to avoid unique constraint violation
        job1 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Software Engineer 1",
            company="TechCorp",
            location="Paris, France",
            description="Software engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job1)
        db.commit()
        db.refresh(job1)

        job2 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Software Engineer 2",
            company="TechCorp",
            location="Paris, France",
            description="Software engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)

        job3 = JobOffer(
            source_id=source.id,
            source_url=f"https://example.com/{uuid.uuid4()}",
            fingerprint=f"test_phase2_job_{uuid.uuid4()}",
            title="Software Engineer 3",
            company="TechCorp",
            location="Paris, France",
            description="Software engineer role",
            contract_type=ContractType.CDI,
            status=OfferStatus.NEW
        )
        db.add(job3)
        db.commit()
        db.refresh(job3)

        # Test ASSISTED mode
        app1 = Application(
            job_offer_id=job1.id,
            user_id=user.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.DRAFT
        )
        db.add(app1)
        db.commit()
        assert app1.mode == ApplicationMode.ASSISTED
        assert app1.status == ApplicationStatus.DRAFT

        # Test SUBMITTING status
        app2 = Application(
            job_offer_id=job2.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.SUBMITTING
        )
        db.add(app2)
        db.commit()
        assert app2.status == ApplicationStatus.SUBMITTING

        # Test ACTION_REQUIRED status
        app3 = Application(
            job_offer_id=job3.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.ACTION_REQUIRED
        )
        db.add(app3)
        db.commit()
        assert app3.status == ApplicationStatus.ACTION_REQUIRED
    finally:
        db.close()
