"""
Phase 3 Application Management Tests: Assisted Workflow + Cover Letter Management.

Covers:
1. Assisted mode workflow (application creation without submission)
2. Cover letter management (GET, PUT, generate)
3. ACTION_REQUIRED behavior and API
4. Status transitions (PENDING_VALIDATION → APPROVED → SUBMITTING → SENT/FAILED/ACTION_REQUIRED)
5. Authorization/ownership protection
6. Rejection behavior
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.exc import IntegrityError

from shared.database import SessionLocal
from user_management.models import User, UserPreferences
from job_sourcing.models import JobOffer, JobSource, SourceType, ContractType, OfferStatus
from cv_management.models import CV, CVStatus
from matching.models import Match
from applications.models import Application, ApplicationMode, ApplicationStatus
from applications.application_service import ApplicationService
from applications.ports.application_channel import IApplicationChannel


@pytest.fixture(autouse=True)
def cleanup_test_records():
    """Cleanup only test records created with test_phase3_ prefix."""
    yield
    db = SessionLocal()
    try:
        # Delete test applications first
        test_apps = (
            db.query(Application)
            .join(User, Application.user_id == User.id)
            .filter(User.email.ilike("test_phase3_%"))
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
            .filter(User.email.ilike("test_phase3_%"))
            .all()
        )
        for m in test_matches:
            db.delete(m)
        db.commit()

        # Delete test CVs
        test_cvs = (
            db.query(CV)
            .join(User, CV.user_id == User.id)
            .filter(User.email.ilike("test_phase3_%"))
            .all()
        )
        for c in test_cvs:
            db.delete(c)
        db.commit()

        # Delete test job offers
        test_jobs = db.query(JobOffer).filter(JobOffer.fingerprint.ilike("test_phase3_%")).all()
        for j in test_jobs:
            db.delete(j)
        db.commit()

        # Delete test job sources
        test_sources = db.query(JobSource).filter(JobSource.name.ilike("test_phase3_%")).all()
        for s in test_sources:
            db.delete(s)
        db.commit()

        # Delete test preferences
        test_prefs = (
            db.query(UserPreferences)
            .join(User, UserPreferences.user_id == User.id)
            .filter(User.email.ilike("test_phase3_%"))
            .all()
        )
        for p in test_prefs:
            db.delete(p)
        db.commit()

        # Delete test users
        test_users = db.query(User).filter(User.email.ilike("test_phase3_%")).all()
        for u in test_users:
            db.delete(u)
        db.commit()
    finally:
        db.close()


def _create_test_source(db):
    source = JobSource(
        name=f"test_phase3_src_{uuid.uuid4().hex[:8]}",
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
        fingerprint=f"test_phase3_job_{uuid.uuid4()}",
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
        email=f"test_phase3_{uuid.uuid4().hex[:8]}@example.com",
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
        semantic_similarity=0.82,
        summary="Strong match with Python/React skills"
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return cv, match


# ─────────────────────────────────────────────────────────────
# 1. Assisted Mode Workflow
# ─────────────────────────────────────────────────────────────
def test_assisted_application_created_without_submission():
    """Test that ASSISTED mode creates application without automatic submission."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set ASSISTED mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="ASSISTED",
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

        # Phase 3: ASSISTED should create with PENDING_VALIDATION status
        assert app.status == ApplicationStatus.PENDING_VALIDATION
        assert app.mode == ApplicationMode.ASSISTED
        assert app.job_offer_id == job.id
        assert app.match_id == match.id

        # Verify channel was NOT called (no automatic submission)
        mock_channel.submit.assert_not_called()
    finally:
        db.close()


def test_assisted_application_remains_pending_until_approval():
    """Test that ASSISTED application remains PENDING_VALIDATION until user approval."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set ASSISTED mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="ASSISTED",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Should still be PENDING_VALIDATION
        assert app.status == ApplicationStatus.PENDING_VALIDATION
        
        # Refresh from DB to confirm
        db.refresh(app)
        assert app.status == ApplicationStatus.PENDING_VALIDATION
    finally:
        db.close()


def test_assisted_approval_triggers_background_submission():
    """Test that approving ASSISTED application triggers background submission."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set ASSISTED mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="ASSISTED",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Approve application
        approved_app = ApplicationService.approve_application(
            application_id=app.id,
            user_id=user.id,
            db=db
        )

        # Should transition to APPROVED
        assert approved_app.status == ApplicationStatus.APPROVED
        assert approved_app.mode == ApplicationMode.ASSISTED

        # Verify no synchronous Playwright execution
        mock_channel.submit.assert_not_called()
    finally:
        db.close()


def test_assisted_approval_does_not_block():
    """Test that approval returns immediately without blocking on Playwright."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set ASSISTED mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="ASSISTED",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Approve application
        start_time = datetime.utcnow()
        approved_app = ApplicationService.approve_application(
            application_id=app.id,
            user_id=user.id,
            db=db
        )
        end_time = datetime.utcnow()

        # Should return almost immediately (no Playwright execution)
        duration = (end_time - start_time).total_seconds()
        assert duration < 1.0  # Should be much faster than Playwright execution
        assert approved_app.status == ApplicationStatus.APPROVED
    finally:
        db.close()


def test_assisted_rejection_prevents_submission():
    """Test that rejecting ASSISTED application prevents submission."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set ASSISTED mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="ASSISTED",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Reject application
        rejected_app = ApplicationService.reject_application(
            application_id=app.id,
            user_id=user.id,
            reason="Not interested",
            db=db
        )

        # Should transition to REJECTED
        assert rejected_app.status == ApplicationStatus.REJECTED
        assert rejected_app.failure_reason == "Not interested"

        # Verify no Playwright execution
        mock_channel.submit.assert_not_called()
    finally:
        db.close()


def test_rejected_application_cannot_be_approved():
    """Test that rejected application cannot later be approved."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set ASSISTED mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="ASSISTED",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Reject application
        ApplicationService.reject_application(
            application_id=app.id,
            user_id=user.id,
            reason="Not interested",
            db=db
        )

        # Try to approve - should fail
        with pytest.raises(Exception) as exc_info:
            ApplicationService.approve_application(
                application_id=app.id,
                user_id=user.id,
                db=db
            )

        assert "Impossible d'approuver une candidature dans l'état" in str(exc_info.value)
    finally:
        db.close()


def test_already_submitted_application_cannot_be_approved():
    """Test that already submitted application cannot be approved again."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Set ASSISTED mode
        prefs = UserPreferences(
            user_id=user.id,
            application_mode="ASSISTED",
            min_match_score=70.0,
            max_applications_per_day=5
        )
        db.add(prefs)
        db.commit()

        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Approve and mark as SENT (simulating completed submission)
        ApplicationService.approve_application(
            application_id=app.id,
            user_id=user.id,
            db=db
        )
        app.status = ApplicationStatus.SENT
        app.submitted_at = datetime.utcnow()
        db.commit()

        # Try to approve again - should fail
        with pytest.raises(Exception) as exc_info:
            ApplicationService.approve_application(
                application_id=app.id,
                user_id=user.id,
                db=db
            )

        assert "Impossible d'approuver une candidature dans l'état" in str(exc_info.value)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 2. Status Transitions
# ─────────────────────────────────────────────────────────────
def test_status_transition_pending_to_approved():
    """Test PENDING_VALIDATION → APPROVED transition."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Create PENDING_VALIDATION application
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()

        # Approve
        approved_app = ApplicationService.approve_application(
            application_id=app.id,
            user_id=user.id,
            db=db
        )

        assert approved_app.status == ApplicationStatus.APPROVED
    finally:
        db.close()


def test_status_transition_approved_to_submitting():
    """Test APPROVED → SUBMITTING transition in background execution."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Create APPROVED application
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.APPROVED
        )
        db.add(app)
        db.commit()

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "SENT",
            "cover_letter": "Test cover letter",
            "execution_logs": {},
            "screenshots": {}
        }

        # Execute submission (simulating background task)
        submitted_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Should transition to SUBMITTING then SENT
        assert submitted_app.status == ApplicationStatus.SENT
    finally:
        db.close()


def test_status_transition_submitting_to_sent():
    """Test SUBMITTING → SENT transition."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

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

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "SENT"
        }

        # Execute submission
        result_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        assert result_app.status == ApplicationStatus.SENT
        assert result_app.submitted_at is not None
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

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": False,
            "error_message": "Connection timeout"
        }

        # Execute submission
        result_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        assert result_app.status == ApplicationStatus.FAILED
        assert result_app.failure_reason == "Connection timeout"
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

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "MANUAL_REQUIRED",
            "error_message": "CAPTCHA detected"
        }

        # Execute submission
        result_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        assert result_app.status == ApplicationStatus.ACTION_REQUIRED
        assert result_app.failure_reason == "CAPTCHA detected"
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 3. Cover Letter Management
# ─────────────────────────────────────────────────────────────
def test_get_cover_letter():
    """Test GET cover letter endpoint."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Create application with cover letter
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION,
            cover_letter="Dear Hiring Manager, I am writing to apply..."
        )
        db.add(app)
        db.commit()

        # Generate cover letter (simulates GET endpoint behavior)
        result_app = ApplicationService.generate_cover_letter_for_application(
            application_id=app.id,
            user_id=user.id,
            db=db
        )

        # Should have cover letter (either existing or regenerated)
        assert result_app.cover_letter is not None
        assert len(result_app.cover_letter) > 10
    finally:
        db.close()


def test_generate_cover_letter():
    """Test cover letter generation for review before submission."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Create application without cover letter
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()

        # Generate cover letter
        result_app = ApplicationService.generate_cover_letter_for_application(
            application_id=app.id,
            user_id=user.id,
            db=db
        )

        assert result_app.cover_letter is not None
        assert len(result_app.cover_letter) > 10
        assert result_app.status == ApplicationStatus.PENDING_VALIDATION
    finally:
        db.close()


def test_update_cover_letter_before_submission():
    """Test PUT cover letter before submission."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Create application
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION,
            cover_letter="Original cover letter"
        )
        db.add(app)
        db.commit()

        # Update cover letter
        updated_app = ApplicationService.update_cover_letter(
            application_id=app.id,
            user_id=user.id,
            cover_letter_content="Updated cover letter",
            db=db
        )

        assert updated_app.cover_letter == "Updated cover letter"
    finally:
        db.close()


def test_update_cover_letter_after_sent_rejected():
    """Test that cover letter cannot be updated after SENT."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Create SENT application
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.SENT,
            submitted_at=datetime.utcnow(),
            cover_letter="Original cover letter"
        )
        db.add(app)
        db.commit()

        # Try to update cover letter - should fail
        with pytest.raises(Exception) as exc_info:
            ApplicationService.update_cover_letter(
                application_id=app.id,
                user_id=user.id,
                cover_letter_content="Updated cover letter",
                db=db
            )

        assert "Impossible de modifier la lettre de motivation" in str(exc_info.value)
    finally:
        db.close()


def test_cover_letter_ownership_protection():
    """Test that unauthorized user cannot access another user's cover letter."""
    db = SessionLocal()
    try:
        user1 = _create_test_user(db)
        user2 = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user1, job)

        # Create application for user1
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user1.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION,
            cover_letter="User1's cover letter"
        )
        db.add(app)
        db.commit()

        # Try to generate cover letter as user2 - should fail
        with pytest.raises(Exception) as exc_info:
            ApplicationService.generate_cover_letter_for_application(
                application_id=app.id,
                user_id=user2.id,
                db=db
            )

        assert "Accès non autorisé" in str(exc_info.value)
    finally:
        db.close()


def test_application_without_cover_letter_handled():
    """Test that application without cover letter is handled correctly."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

        # Create application without cover letter
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()

        # Should return None for cover letter
        assert app.cover_letter is None

        # Generate cover letter
        result_app = ApplicationService.generate_cover_letter_for_application(
            application_id=app.id,
            user_id=user.id,
            db=db
        )

        # Should now have a cover letter
        assert result_app.cover_letter is not None
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 4. ACTION_REQUIRED Behavior
# ─────────────────────────────────────────────────────────────
def test_captcha_results_in_action_required():
    """Test that CAPTCHA/manual intervention results in ACTION_REQUIRED."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

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

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "MANUAL_REQUIRED",
            "error_message": "CAPTCHA required",
            "screenshots": {"step1": "/static/screenshots/app/test/step1.png"},
            "execution_logs": [{"step": "CAPTCHA", "message": "Detected CAPTCHA"}]
        }

        # Execute submission
        result_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        assert result_app.status == ApplicationStatus.ACTION_REQUIRED
        assert result_app.failure_reason == "CAPTCHA required"
        assert result_app.screenshots is not None
        assert result_app.execution_logs is not None
    finally:
        db.close()


def test_action_required_not_application_failed():
    """Test that ACTION_REQUIRED does not become APPLICATION_FAILED."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

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

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "MANUAL_REQUIRED",
            "error_message": "CAPTCHA required"
        }

        # Execute submission
        result_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Should be ACTION_REQUIRED, not FAILED
        assert result_app.status == ApplicationStatus.ACTION_REQUIRED
        assert result_app.status != ApplicationStatus.FAILED
    finally:
        db.close()


def test_action_required_notification_generated():
    """Test that ACTION_REQUIRED notification is generated."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

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

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "MANUAL_REQUIRED",
            "error_message": "CAPTCHA required"
        }

        # Execute submission
        result_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Check for ACTION_REQUIRED notification
        from notifications.models import Notification, NotificationType
        notification = db.query(Notification).filter_by(
            user_id=user.id,
            type=NotificationType.ACTION_REQUIRED,
            related_application_id=app.id
        ).first()

        assert notification is not None
        assert "Action requise" in notification.message
    finally:
        db.close()


def test_action_required_information_preserved():
    """Test that useful action information is preserved."""
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user, job)

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

        mock_channel = Mock(spec=IApplicationChannel)
        mock_channel.submit.return_value = {
            "success": True,
            "status": "MANUAL_REQUIRED",
            "error_message": "Verification code required",
            "screenshots": {
                "step1_opened": "/static/screenshots/app/test/step1.png",
                "step2_filled": "/static/screenshots/app/test/step2.png"
            },
            "execution_logs": [
                {"step": "1_COVER_LETTER", "message": "Generated cover letter"},
                {"step": "4_BLOCK_CHECK", "message": "Verification code detected"}
            ]
        }

        # Execute submission
        result_app = ApplicationService.execute_submission(
            application_id=app.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Information should be preserved
        assert result_app.status == ApplicationStatus.ACTION_REQUIRED
        assert result_app.failure_reason == "Verification code required"
        assert result_app.screenshots is not None
        assert len(result_app.screenshots) == 2
        assert result_app.execution_logs is not None
        assert len(result_app.execution_logs) == 2
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 5. Authorization/Ownership Protection
# ─────────────────────────────────────────────────────────────
def test_approve_application_ownership_protection():
    """Test that user cannot approve another user's application."""
    db = SessionLocal()
    try:
        user1 = _create_test_user(db)
        user2 = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user1, job)

        # Create application for user1
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user1.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()

        # Try to approve as user2 - should fail
        with pytest.raises(Exception) as exc_info:
            ApplicationService.approve_application(
                application_id=app.id,
                user_id=user2.id,
                db=db
            )

        assert "Accès non autorisé" in str(exc_info.value)
    finally:
        db.close()


def test_reject_application_ownership_protection():
    """Test that user cannot reject another user's application."""
    db = SessionLocal()
    try:
        user1 = _create_test_user(db)
        user2 = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user1, job)

        # Create application for user1
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user1.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()

        # Try to reject as user2 - should fail
        with pytest.raises(Exception) as exc_info:
            ApplicationService.reject_application(
                application_id=app.id,
                user_id=user2.id,
                reason="Not interested",
                db=db
            )

        assert "Accès non autorisé" in str(exc_info.value)
    finally:
        db.close()


def test_cover_letter_ownership_protection_get():
    """Test that user cannot get another user's cover letter."""
    db = SessionLocal()
    try:
        user1 = _create_test_user(db)
        user2 = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user1, job)

        # Create application for user1
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user1.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION,
            cover_letter="User1's cover letter"
        )
        db.add(app)
        db.commit()

        # Try to generate cover letter as user2 - should fail
        with pytest.raises(Exception) as exc_info:
            ApplicationService.generate_cover_letter_for_application(
                application_id=app.id,
                user_id=user2.id,
                db=db
            )

        assert "Accès non autorisé" in str(exc_info.value)
    finally:
        db.close()


def test_cover_letter_ownership_protection_update():
    """Test that user cannot update another user's cover letter."""
    db = SessionLocal()
    try:
        user1 = _create_test_user(db)
        user2 = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)
        _, match = _create_test_cv_and_match(db, user1, job)

        # Create application for user1
        app = Application(
            job_offer_id=job.id,
            match_id=match.id,
            user_id=user1.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION,
            cover_letter="User1's cover letter"
        )
        db.add(app)
        db.commit()

        # Try to update cover letter as user2 - should fail
        with pytest.raises(Exception) as exc_info:
            ApplicationService.update_cover_letter(
                application_id=app.id,
                user_id=user2.id,
                cover_letter_content="Malicious update",
                db=db
            )

        assert "Accès non autorisé" in str(exc_info.value)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 6. Manual Mode Preservation
# ─────────────────────────────────────────────────────────────
def test_manual_mode_requires_approval():
    """Test that MANUAL mode still requires explicit approval."""
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

        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Should create with PENDING_VALIDATION status
        assert app.status == ApplicationStatus.PENDING_VALIDATION
        assert app.mode == ApplicationMode.MANUAL_VALIDATION

        # Verify no automatic submission
        mock_channel.submit.assert_not_called()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 7. Full Auto Preservation
# ─────────────────────────────────────────────────────────────
def test_full_auto_mode_background_submission():
    """Test that FULL_AUTO mode still uses background submission."""
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

        mock_channel = Mock(spec=IApplicationChannel)

        # Create application
        app = ApplicationService.process_match(
            match_id=match.id,
            user_id=user.id,
            application_channel=mock_channel,
            db=db
        )

        # Should create with SUBMITTING status for background execution
        assert app.status == ApplicationStatus.SUBMITTING
        assert app.mode == ApplicationMode.FULL_AUTO

        # Verify no synchronous Playwright execution
        mock_channel.submit.assert_not_called()
    finally:
        db.close()
