"""
Phase 1 Application Management Tests: Database Integrity & Schema.

Covers:
1. Application correctly linked to JobOffer via job_offer_id.
2. Match deletion does NOT delete Application (ON DELETE SET NULL).
3. Duplicate protection: unique constraint on (user_id, job_offer_id).
4. Multiple users can apply to same JobOffer.
5. Same user can apply to different JobOffers.
6. ASSISTED mode in ApplicationMode enum.
7. DRAFT, SUBMITTING, ACTION_REQUIRED in ApplicationStatus enum.
8. ACTION_REQUIRED in NotificationType enum.
9. JobOffer deletion with active application is RESTRICTED.
10. Schema serialization via ApplicationResponse works with new fields.
"""
import uuid
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from shared.database import SessionLocal
from user_management.models import User
from job_sourcing.models import JobOffer, JobSource, SourceType, ContractType, OfferStatus
from cv_management.models import CV, CVStatus
from matching.models import Match
from applications.models import Application, ApplicationMode, ApplicationStatus
from applications.schemas import ApplicationResponse
from notifications.models import Notification, NotificationType


@pytest.fixture(autouse=True)
def cleanup_test_records():
    """Cleanup only test records created with test_app_schema_ prefix."""
    yield
    db = SessionLocal()
    try:
        # Delete test applications first
        test_apps = (
            db.query(Application)
            .join(User, Application.user_id == User.id)
            .filter(User.email.ilike("test_app_schema_%"))
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
            .filter(User.email.ilike("test_app_schema_%"))
            .all()
        )
        for m in test_matches:
            db.delete(m)
        db.commit()

        # Delete test CVs
        test_cvs = (
            db.query(CV)
            .join(User, CV.user_id == User.id)
            .filter(User.email.ilike("test_app_schema_%"))
            .all()
        )
        for c in test_cvs:
            db.delete(c)
        db.commit()

        # Delete test job offers
        test_jobs = db.query(JobOffer).filter(JobOffer.fingerprint.ilike("test_app_schema_%")).all()
        for j in test_jobs:
            db.delete(j)
        db.commit()

        # Delete test job sources
        test_sources = db.query(JobSource).filter(JobSource.name.ilike("test_app_schema_%")).all()
        for s in test_sources:
            db.delete(s)
        db.commit()

        # Delete test notifications
        test_notifs = (
            db.query(Notification)
            .join(User, Notification.user_id == User.id)
            .filter(User.email.ilike("test_app_schema_%"))
            .all()
        )
        for n in test_notifs:
            db.delete(n)
        db.commit()

        # Delete test users
        test_users = db.query(User).filter(User.email.ilike("test_app_schema_%")).all()
        for u in test_users:
            db.delete(u)
        db.commit()
    finally:
        db.close()


def _create_test_source(db):
    source = JobSource(
        name=f"test_app_schema_src_{uuid.uuid4().hex[:8]}",
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
        fingerprint=f"test_app_schema_job_{uuid.uuid4()}",
        title="DevOps Engineer",
        company="Acme Corp",
        location="Paris, France",
        description="DevOps engineer role",
        contract_type=ContractType.CDI,
        status=OfferStatus.NEW
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _create_test_user(db):
    user = User(
        email=f"test_app_schema_{uuid.uuid4().hex[:8]}@example.com",
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
# 1. Application gets correct job_offer_id
# ─────────────────────────────────────────────────────────────
def test_application_has_correct_job_offer_id():
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
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()
        db.refresh(app)

        assert app.job_offer_id == job.id
        assert app.match_id == match.id
        assert app.user_id == user.id
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 2. Deleting / replacing Match does NOT delete Application (SET NULL)
# ─────────────────────────────────────────────────────────────
def test_deleting_match_does_not_delete_application():
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

        # Delete the match row (simulating CV reparsing or match recomputation)
        db.delete(match)
        db.commit()

        # Verify application still exists and match_id was set to NULL
        surviving_app = db.get(Application, app_id)
        assert surviving_app is not None
        assert surviving_app.job_offer_id == job.id
        assert surviving_app.match_id is None
        assert surviving_app.status == ApplicationStatus.SENT
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 3. Duplicate protection: unique constraint on (user_id, job_offer_id)
# ─────────────────────────────────────────────────────────────
def test_same_user_cannot_create_two_applications_for_same_job():
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

        # Second application for same user and same job must fail at DB level
        app2 = Application(
            job_offer_id=job.id,
            user_id=user.id,
            mode=ApplicationMode.FULL_AUTO,
            status=ApplicationStatus.APPROVED
        )
        db.add(app2)
        with pytest.raises(IntegrityError) as exc_info:
            db.commit()

        db.rollback()
        assert "uq_user_job_application" in str(exc_info.value).lower()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 4. Different users can apply to the same JobOffer
# ─────────────────────────────────────────────────────────────
def test_different_users_can_apply_to_same_job():
    db = SessionLocal()
    try:
        user1 = _create_test_user(db)
        user2 = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)

        app1 = Application(
            job_offer_id=job.id,
            user_id=user1.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        app2 = Application(
            job_offer_id=job.id,
            user_id=user2.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app1)
        db.add(app2)
        db.commit()

        assert app1.id != app2.id
        assert app1.job_offer_id == job.id
        assert app2.job_offer_id == job.id
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 5. Same user can apply to different JobOffers
# ─────────────────────────────────────────────────────────────
def test_same_user_can_apply_to_different_jobs():
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job1 = _create_test_job(db, source.id)
        job2 = _create_test_job(db, source.id)

        app1 = Application(
            job_offer_id=job1.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        app2 = Application(
            job_offer_id=job2.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app1)
        db.add(app2)
        db.commit()

        assert app1.job_offer_id == job1.id
        assert app2.job_offer_id == job2.id
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 6. ASSISTED mode in ApplicationMode works
# ─────────────────────────────────────────────────────────────
def test_assisted_enum_works():
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)

        app = Application(
            job_offer_id=job.id,
            user_id=user.id,
            mode=ApplicationMode.ASSISTED,
            status=ApplicationStatus.PENDING_VALIDATION
        )
        db.add(app)
        db.commit()
        db.refresh(app)

        assert app.mode == ApplicationMode.ASSISTED
        assert app.mode.value == "ASSISTED"
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 7. DRAFT, SUBMITTING, ACTION_REQUIRED statuses work
# ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("test_status", [
    ApplicationStatus.DRAFT,
    ApplicationStatus.SUBMITTING,
    ApplicationStatus.ACTION_REQUIRED,
    ApplicationStatus.PENDING_VALIDATION,
    ApplicationStatus.APPROVED,
    ApplicationStatus.SENT,
    ApplicationStatus.FAILED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.MANUAL_REQUIRED,
])
def test_application_statuses_work(test_status):
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)

        app = Application(
            job_offer_id=job.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=test_status
        )
        db.add(app)
        db.commit()
        db.refresh(app)

        assert app.status == test_status
        assert app.status.value == test_status.value
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 8. ACTION_REQUIRED in NotificationType works
# ─────────────────────────────────────────────────────────────
def test_action_required_notification_enum_works():
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        notif = Notification(
            user_id=user.id,
            type=NotificationType.ACTION_REQUIRED,
            message="Human intervention required: CAPTCHA detected."
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        assert notif.type == NotificationType.ACTION_REQUIRED
        assert notif.type.value == "ACTION_REQUIRED"
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 9. JobOffer deletion with active Application is RESTRICTED
# ─────────────────────────────────────────────────────────────
def test_job_offer_deletion_is_restricted():
    db = SessionLocal()
    try:
        user = _create_test_user(db)
        source = _create_test_source(db)
        job = _create_test_job(db, source.id)

        app = Application(
            job_offer_id=job.id,
            user_id=user.id,
            mode=ApplicationMode.MANUAL_VALIDATION,
            status=ApplicationStatus.SENT
        )
        db.add(app)
        db.commit()

        # Deleting job_offer must be prevented by FK RESTRICT
        db.delete(job)
        with pytest.raises(IntegrityError) as exc_info:
            db.commit()

        db.rollback()
        assert "fk_applications_job_offer_id" in str(exc_info.value).lower() or "violates foreign key constraint" in str(exc_info.value).lower()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# 10. ApplicationResponse Pydantic schema serialization
# ─────────────────────────────────────────────────────────────
def test_schema_serialization():
    app_id = uuid.uuid4()
    job_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.utcnow()

    # Case A: With match_id
    match_id = uuid.uuid4()
    schema_with_match = ApplicationResponse(
        id=app_id,
        job_offer_id=job_id,
        match_id=match_id,
        user_id=user_id,
        mode=ApplicationMode.ASSISTED,
        status=ApplicationStatus.DRAFT,
        created_at=now
    )
    assert schema_with_match.job_offer_id == job_id
    assert schema_with_match.match_id == match_id
    assert schema_with_match.mode == ApplicationMode.ASSISTED
    assert schema_with_match.status == ApplicationStatus.DRAFT

    # Case B: Without match_id (SET NULL after match deletion)
    schema_without_match = ApplicationResponse(
        id=app_id,
        job_offer_id=job_id,
        match_id=None,
        user_id=user_id,
        mode=ApplicationMode.FULL_AUTO,
        status=ApplicationStatus.ACTION_REQUIRED,
        created_at=now
    )
    assert schema_without_match.job_offer_id == job_id
    assert schema_without_match.match_id is None
    assert schema_without_match.status == ApplicationStatus.ACTION_REQUIRED
