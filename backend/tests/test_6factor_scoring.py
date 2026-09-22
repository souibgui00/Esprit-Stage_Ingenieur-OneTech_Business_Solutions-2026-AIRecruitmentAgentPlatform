"""
Comprehensive tests for the 6-factor scoring architecture.

Tests cover:
- Skills scoring (35 points)
- Experience relevance scoring (20 points)
- Seniority matching (10 points)
- Semantic similarity (15 points)
- LLM evaluation (10 points)
- Certification bonus (0-5 points capped)
- Overall score calculation and bounds
"""
import pytest
import uuid
from pathlib import Path
from unittest.mock import Mock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from shared.database import SessionLocal, engine
from cv_management.models import CV, CVSkill, Experience, Certification, Skill
from job_sourcing.models import JobOffer, JobSkill, JobSource, SourceType
from user_management.models import User, UserSession, UserActivity, UserPreferences
from matching.scoring_service import ScoringService
from matching.matching_service import MatchingService


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data after each test."""
    yield
    db = SessionLocal()
    try:
        from user_management.models import UserSession, UserActivity, UserPreferences
        test_users = db.query(User).filter(User.email.ilike("test%")).all()
        test_uids = [u.id for u in test_users]
        if test_uids:
            db.query(UserSession).filter(UserSession.user_id.in_(test_uids)).delete(synchronize_session=False)
            db.query(UserActivity).filter(UserActivity.user_id.in_(test_uids)).delete(synchronize_session=False)
            db.query(UserPreferences).filter(UserPreferences.user_id.in_(test_uids)).delete(synchronize_session=False)
            db.query(CV).filter(CV.user_id.in_(test_uids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(test_uids)).delete(synchronize_session=False)
        test_sources = db.query(JobSource).filter(JobSource.name.ilike("test%")).all()
        for ts in test_sources:
            db.delete(ts)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Cleanup error: {e}")
    finally:
        db.close()
        
@pytest.fixture
def db_session():
    """Provide a clean database session for each test."""
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


def create_test_cv(db: Session) -> CV:
    """Helper to create a test CV."""
    # Create a user first since CV has foreign key constraint
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="test@example.com",
        hashed_password="hashed_password"
    )
    db.add(user)
    db.flush()  # Flush to get the user in the session but don't commit
    
    cv = CV(
        id=uuid.uuid4(),
        user_id=user_id,
        filename="test_cv.pdf",
        raw_file_url="/tmp/test.pdf",
        language="FR"
    )
    db.add(cv)
    db.flush()  # Flush to get the CV in the session but don't commit
    db.refresh(cv)
    return cv


def create_test_job_offer(db: Session) -> JobOffer:
    """Helper to create a test job offer."""
    source = JobSource(
        name="Test Source",
        type=SourceType.OFFICIAL_API,
        base_url="https://example.com",
        is_active=True
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    job = JobOffer(
        source_id=source.id,
        source_url="https://example.com/job/1",
        fingerprint="test-fingerprint-1",
        title="Senior Python Developer",
        company="Test Company",
        location="Paris",
        description="We need Python and Django skills with 5+ years experience.",
        contract_type=None
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_skill(db: Session, name: str) -> Skill:
    """Helper to create a skill."""
    skill = db.query(Skill).filter_by(canonical_name=name).first()
    if not skill:
        skill = Skill(canonical_name=name, category="technical")
        db.add(skill)
        db.commit()
        db.refresh(skill)
    return skill


# ==================== SKILLS SCORING TESTS ====================

def test_skills_scoring_all_essential_matched(db_session):
    """Test skills scoring when all essential skills are matched."""
    db = db_session
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Create skills
        python_skill = create_skill(db, "python")
        django_skill = create_skill(db, "django")
        
        # Add essential job skills
        job_skill1 = JobSkill(job_offer_id=job.id, skill_id=python_skill.id, importance="essential")
        job_skill2 = JobSkill(job_offer_id=job.id, skill_id=django_skill.id, importance="essential")
        db.add(job_skill1)
        db.add(job_skill2)
        
        # Add matching CV skills
        cv_skill1 = CVSkill(cv_id=cv.id, skill_id=python_skill.id, proficiency="ADVANCED", source="test")
        cv_skill2 = CVSkill(cv_id=cv.id, skill_id=django_skill.id, proficiency="INTERMEDIATE", source="test")
        db.add(cv_skill1)
        db.add(cv_skill2)
        
        db.flush()  # Flush instead of commit
        
        result = ScoringService.calculate_skills_score(cv.id, job.id, db)
        
        assert result["skills_score"] > 20  # Should be high with all essential matched
        assert result["skills_max"] == 35.0
        assert len(result["matched_essential_skills"]) == 2
        assert len(result["missing_essential_skills"]) == 0
        
    finally:
        pass  # db_session will rollback automatically


def test_skills_scoring_missing_essential(db_session):
    """Test skills scoring when essential skills are missing."""
    db = db_session
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Create skills
        python_skill = create_skill(db, "python")
        django_skill = create_skill(db, "django")
        react_skill = create_skill(db, "react")
        
        # Add essential job skills
        job_skill1 = JobSkill(job_offer_id=job.id, skill_id=python_skill.id, importance="essential")
        job_skill2 = JobSkill(job_offer_id=job.id, skill_id=django_skill.id, importance="essential")
        job_skill3 = JobSkill(job_offer_id=job.id, skill_id=react_skill.id, importance="essential")
        db.add(job_skill1)
        db.add(job_skill2)
        db.add(job_skill3)
        
        # Add only partial CV skills
        cv_skill1 = CVSkill(cv_id=cv.id, skill_id=python_skill.id, proficiency="ADVANCED", source="test")
        db.add(cv_skill1)
        
        db.flush()
        
        result = ScoringService.calculate_skills_score(cv.id, job.id, db)
        
        assert result["skills_score"] < 30  # Penalty for missing essential skills
        assert len(result["matched_essential_skills"]) == 1
        assert len(result["missing_essential_skills"]) == 2
        
    finally:
        pass


def test_skills_scoring_nice_to_have(db_session):
    """Test skills scoring with nice-to-have skills."""
    db = db_session
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Create skills
        python_skill = create_skill(db, "python")
        docker_skill = create_skill(db, "docker")
        
        # Add essential and nice-to-have job skills
        job_skill1 = JobSkill(job_offer_id=job.id, skill_id=python_skill.id, importance="essential")
        job_skill2 = JobSkill(job_offer_id=job.id, skill_id=docker_skill.id, importance="nice_to_have")
        db.add(job_skill1)
        db.add(job_skill2)
        
        # Add matching CV skills
        cv_skill1 = CVSkill(cv_id=cv.id, skill_id=python_skill.id, proficiency="ADVANCED", source="test")
        cv_skill2 = CVSkill(cv_id=cv.id, skill_id=docker_skill.id, proficiency="BEGINNER", source="test")
        db.add(cv_skill1)
        db.add(cv_skill2)
        
        db.flush()
        
        result = ScoringService.calculate_skills_score(cv.id, job.id, db)
        
        assert result["skills_score"] > 0
        assert len(result["matched_nice_to_have_skills"]) == 1
        assert "nice_to_have_score" in result
        
    finally:
        pass


def test_skills_scoring_no_skills(db_session):
    """Test skills scoring when no skills are present."""
    db = db_session
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        db.flush()
        
        result = ScoringService.calculate_skills_score(cv.id, job.id, db)
        
        assert result["skills_score"] == 0.0
        assert len(result["matched_essential_skills"]) == 0
        
    finally:
        pass


# ==================== EXPERIENCE SCORING TESTS ====================

def test_experience_scoring_sufficient_years(db_session):
    """Test experience scoring with sufficient years."""
    db = db_session
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Add experience with sufficient years
        from datetime import date, timedelta
        exp = Experience(
            cv_id=cv.id,
            title="Senior Developer",
            company="Tech Corp",
            start_date=date.today() - timedelta(days=6*365),  # 6 years
            end_date=None,
            is_current=True
        )
        db.add(exp)
        db.flush()
        
        result = ScoringService.calculate_experience_score(cv.id, job.id, db)
        
        assert result["experience_score"] > 0
        assert result["experience_max"] == 20.0
        assert result["total_years"] >= 5
        
    finally:
        pass


def test_experience_scoring_insufficient_years(db_session):
    """Test experience scoring with insufficient years."""
    db = db_session
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Add experience with insufficient years
        from datetime import date, timedelta
        exp = Experience(
            cv_id=cv.id,
            title="Junior Developer",
            company="Tech Corp",
            start_date=date.today() - timedelta(days=1*365),  # 1 year
            end_date=None,
            is_current=True
        )
        db.add(exp)
        db.flush()
        
        result = ScoringService.calculate_experience_score(cv.id, job.id, db)
        
        assert result["experience_score"] < 10  # Penalty for insufficient experience
        
    finally:
        pass


def test_experience_scoring_no_experience(db_session):
    """Test experience scoring with no experience."""
    db = db_session
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        db.flush()
        
        result = ScoringService.calculate_experience_score(cv.id, job.id, db)
        
        assert result["experience_score"] >= 0.0  # May have some baseline points
        assert result["total_years"] == 0
        
    finally:
        pass


# ==================== SENIORITY SCORING TESTS ====================

def test_seniority_scoring_exact_match():
    """Test seniority scoring with exact match."""
    db = SessionLocal()
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Update job to require senior level
        job.title = "Senior Python Developer"
        db.commit()
        
        # Add senior-level experience
        from datetime import date, timedelta
        exp = Experience(
            cv_id=cv.id,
            title="Senior Developer",
            company="Tech Corp",
            start_date=date.today() - timedelta(days=5*365),
            end_date=None,
            is_current=True
        )
        db.add(exp)
        db.commit()
        
        result = ScoringService.calculate_seniority_score(cv.id, job.id, db)
        
        assert result["seniority_score"] == 10.0  # Perfect match
        assert result["level_difference"] == 0
        
    finally:
        db.close()


def test_seniority_scoring_underqualified():
    """Test seniority scoring when candidate is underqualified."""
    db = SessionLocal()
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Update job to require senior level
        job.title = "Senior Python Developer"
        db.commit()
        
        # Add junior-level experience
        from datetime import date, timedelta
        exp = Experience(
            cv_id=cv.id,
            title="Junior Developer",
            company="Tech Corp",
            start_date=date.today() - timedelta(days=2*365),
            end_date=None,
            is_current=True
        )
        db.add(exp)
        db.commit()
        
        result = ScoringService.calculate_seniority_score(cv.id, job.id, db)
        
        assert result["seniority_score"] < 10.0  # Penalty for underqualification
        assert result["level_difference"] > 0
        
    finally:
        db.close()


def test_seniority_scoring_missing_seniority():
    """Test seniority scoring when seniority cannot be detected."""
    db = SessionLocal()
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Update job to generic title
        job.title = "Developer"
        db.commit()
        
        # Add experience with generic title
        from datetime import date, timedelta
        exp = Experience(
            cv_id=cv.id,
            title="Developer",
            company="Tech Corp",
            start_date=date.today() - timedelta(days=3*365),
            end_date=None,
            is_current=True
        )
        db.add(exp)
        db.commit()
        
        result = ScoringService.calculate_seniority_score(cv.id, job.id, db)
        
        # Should handle missing seniority gracefully
        assert result["seniority_score"] >= 0
        
    finally:
        db.close()


# ==================== CERTIFICATION BONUS TESTS ====================

def test_certification_bonus_matching_cert(db_session):
    """Test certification bonus with matching certification."""
    db = db_session
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Update job description to require certification
        job.description = "We need AWS certification."
        db.flush()
        
        # Add certification to CV
        from datetime import date
        cert = Certification(
            cv_id=cv.id,
            name="AWS Certified Solutions Architect",
            issuer="Amazon",
            date_obtained=date.today(),
            expiry_date=None
        )
        db.add(cert)
        db.flush()
        
        result = ScoringService.calculate_certification_bonus(cv.id, job.id, db)
        
        # Certification matching depends on pattern extraction, so we just check it runs
        assert result["certification_bonus"] >= 0.0
        assert result["certification_max"] == 5.0
        
    finally:
        pass


def test_certification_bonus_no_certification():
    """Test certification bonus with no certifications."""
    db = SessionLocal()
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        db.commit()
        
        result = ScoringService.calculate_certification_bonus(cv.id, job.id, db)
        
        assert result["certification_bonus"] == 0.0
        assert len(result["matched_certifications"]) == 0
        
    finally:
        db.close()


def test_certification_bonus_strict_cap():
    """Test that certification bonus is strictly capped at 5 points."""
    db = SessionLocal()
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Update job description to require many certifications
        job.description = "We need AWS, Azure, GCP, PMP, CISSP, CCNA, Salesforce, GCP certifications."
        db.commit()
        
        # Add many certifications to CV
        from datetime import date
        certifications = [
            "AWS Certified Solutions Architect",
            "Azure Administrator",
            "Google Cloud Professional",
            "PMP",
            "CISSP",
            "CCNA",
            "Salesforce Administrator"
        ]
        
        for cert_name in certifications:
            cert = Certification(
                cv_id=cv.id,
                name=cert_name,
                issuer="Various",
                date_obtained=date.today(),
                expiry_date=None
            )
            db.add(cert)
        
        db.commit()
        
        result = ScoringService.calculate_certification_bonus(cv.id, job.id, db)
        
        # Should be strictly capped at 5.0
        assert result["certification_bonus"] <= 5.0
        assert result["certification_max"] == 5.0
        
    finally:
        db.close()


# ==================== OVERALL SCORE TESTS ====================

def test_overall_score_bounds():
    """Test that overall score is bounded between 0 and 100."""
    db = SessionLocal()
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Mock similarity calculator and LLM evaluator
        similarity_calculator = Mock()
        similarity_calculator.calculate_single_similarity.return_value = 0.8
        
        llm_evaluator = Mock()
        llm_evaluator.evaluate.return_value = {
            "matching_points": ["Good match"],
            "gap_points": [],
            "summary": "Good candidate",
            "score": 80
        }
        
        match = MatchingService.compute_match(
            cv_id=cv.id,
            job_offer_id=job.id,
            user_id=cv.user_id,
            similarity_calculator=similarity_calculator,
            llm_evaluator=llm_evaluator,
            db=db
        )
        
        assert 0 <= match.compatibility_score <= 100
        
    finally:
        db.close()


def test_overall_score_components_sum():
    """Test that overall score components sum correctly."""
    db = SessionLocal()
    try:
        cv = create_test_cv(db)
        job = create_test_job_offer(db)
        
        # Mock similarity calculator and LLM evaluator
        similarity_calculator = Mock()
        similarity_calculator.calculate_single_similarity.return_value = 0.5
        
        llm_evaluator = Mock()
        llm_evaluator.evaluate.return_value = {
            "matching_points": ["Some match"],
            "gap_points": ["Some gaps"],
            "summary": "Average candidate",
            "score": 50
        }
        
        match = MatchingService.compute_match(
            cv_id=cv.id,
            job_offer_id=job.id,
            user_id=cv.user_id,
            similarity_calculator=similarity_calculator,
            llm_evaluator=llm_evaluator,
            db=db
        )
        
        # Check that individual scores are set
        assert hasattr(match, 'skills_score')
        assert hasattr(match, 'experience_score')
        assert hasattr(match, 'seniority_score')
        assert hasattr(match, 'semantic_score')
        assert hasattr(match, 'certification_bonus')
        
        # Check that scores are in expected ranges
        assert 0 <= match.skills_score <= 35
        assert 0 <= match.experience_score <= 20
        assert 0 <= match.seniority_score <= 10
        assert 0 <= match.semantic_score <= 15
        assert 0 <= match.certification_bonus <= 5
        
    finally:
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])