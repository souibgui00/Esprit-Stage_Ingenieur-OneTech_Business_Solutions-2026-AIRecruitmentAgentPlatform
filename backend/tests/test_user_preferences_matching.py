"""
Tests for UserPreferences integration in MatchingService.
Tests the passes_user_preferences function and integration with get_best_matches_for_cv.
"""
import pytest
import uuid
from unittest.mock import Mock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from shared.database import SessionLocal
from user_management.models import User, UserPreferences
from job_sourcing.models import JobOffer, JobSource, SourceType, ContractType
from matching.matching_service import MatchingService


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data after each test without wiping real database inventory."""
    yield
    db = SessionLocal()
    try:
        from user_management.models import UserSession, UserActivity
        # Clean only test source and its cascade-deleted test offers
        test_sources = db.query(JobSource).filter(JobSource.name == "Test Source").all()
        for ts in test_sources:
            db.delete(ts)
        # Clean only test user and cascade-deleted test preferences/sessions
        test_users = db.query(User).filter(User.email == "test@example.com").all()
        for tu in test_users:
            db.delete(tu)
        db.commit()
    finally:
        db.close()


def create_test_user(db: Session) -> User:
    """Helper to create a test user."""
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_job_source(db: Session) -> JobSource:
    """Helper to create a test job source."""
    source = JobSource(
        name="Test Source",
        type=SourceType.OFFICIAL_API,
        base_url="https://example.com",
        is_active=True
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def create_test_job(db: Session, source: JobSource, location: str = None, contract_type: ContractType = None) -> JobOffer:
    """Helper to create a test job offer."""
    job = JobOffer(
        source_id=source.id,
        source_url="https://example.com/job/1",
        fingerprint="test-fingerprint-1",
        title="Test Job",
        company="Test Company",
        location=location,
        description="Test description",
        contract_type=contract_type
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ==================== UNIT TESTS FOR passes_user_preferences ====================

def test_passes_user_preferences_no_preferences():
    """Test that jobs pass when user has no preferences."""
    job = Mock(spec=JobOffer)
    job.location = "Paris"
    job.contract_type = ContractType.CDI
    
    result = MatchingService.passes_user_preferences(job, None)
    assert result is True


def test_passes_user_preferences_location_match_exact():
    """Test location matching with exact match."""
    job = Mock(spec=JobOffer)
    job.location = "Paris, France"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = ["Paris"]
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_location_match_partial():
    """Test location matching with partial/substring match."""
    job = Mock(spec=JobOffer)
    job.location = "Remote (Paris)"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = ["Paris"]
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_location_mismatch():
    """Test location mismatch."""
    job = Mock(spec=JobOffer)
    job.location = "Lyon"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = ["Paris"]
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is False


def test_passes_user_preferences_multiple_locations_or_logic():
    """Test that ANY preferred location can match."""
    job = Mock(spec=JobOffer)
    job.location = "Lyon"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = ["Paris", "Lyon", "Marseille"]
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_location_missing_job_data():
    """Test graceful degradation when job has no location."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = ["Paris"]
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_location_missing_user_data():
    """Test no filtering when user has no location preferences."""
    job = Mock(spec=JobOffer)
    job.location = "Paris"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_contract_match():
    """Test contract type match."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = ContractType.CDI
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = ["CDI"]
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_contract_mismatch():
    """Test contract type mismatch."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = ContractType.CDD
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = ["CDI"]
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is False


def test_passes_user_preferences_contract_multiple_or_logic():
    """Test that ANY preferred contract type can match."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = ContractType.FREELANCE
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = ["CDI", "FREELANCE"]
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_contract_missing_job_data():
    """Test graceful degradation when job has no contract type."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = ["CDI"]
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_contract_missing_user_data():
    """Test no filtering when user has no contract preferences."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = ContractType.CDI
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_remote_true_with_remote_job():
    """Test remote_preference=True with remote job."""
    job = Mock(spec=JobOffer)
    job.location = "Remote (Paris)"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = True
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_remote_true_with_onsite_job():
    """Test remote_preference=True with onsite job."""
    job = Mock(spec=JobOffer)
    job.location = "Paris"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = True
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is False


def test_passes_user_preferences_remote_true_with_hybrid_job():
    """Test remote_preference=True with hybrid job."""
    job = Mock(spec=JobOffer)
    job.location = "Hybrid (Paris)"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = True
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_remote_false_with_remote_job():
    """Test remote_preference=False with remote job (candidate open to all locations)."""
    job = Mock(spec=JobOffer)
    job.location = "Remote (Paris)"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = False
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_remote_false_with_onsite_job():
    """Test remote_preference=False with onsite job."""
    job = Mock(spec=JobOffer)
    job.location = "Paris"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = False
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_remote_false_with_hybrid_job():
    """Test remote_preference=False with hybrid job."""
    job = Mock(spec=JobOffer)
    job.location = "Hybrid (Paris)"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = False
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_remote_preference_missing_location():
    """Test graceful degradation when job has no location with remote preference."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = True
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_combined_all_match():
    """Test combined preferences when all match."""
    job = Mock(spec=JobOffer)
    job.location = "Paris"
    job.contract_type = ContractType.CDI
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = ["Paris"]
    prefs.preferred_contract_types = ["CDI"]
    prefs.remote_preference = False
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_combined_one_fails():
    """Test combined preferences when one fails."""
    job = Mock(spec=JobOffer)
    job.location = "Lyon"
    job.contract_type = ContractType.CDI
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = ["Paris"]
    prefs.preferred_contract_types = ["CDI"]
    prefs.remote_preference = False
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is False


def test_passes_user_preferences_contract_case_insensitive():
    """Test contract type comparison is case-insensitive."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = ContractType.CDI
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = ["cdi"]  # lowercase
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_contract_whitespace_stripped():
    """Test contract type values are stripped of whitespace."""
    job = Mock(spec=JobOffer)
    job.location = None
    job.contract_type = ContractType.CDI
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = [" CDI ", "  FREELANCE  "]  # with whitespace
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_location_case_insensitive():
    """Test location comparison is case-insensitive."""
    job = Mock(spec=JobOffer)
    job.location = "PARIS, FRANCE"
    job.contract_type = None
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = ["paris"]  # lowercase
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_empty_preference_arrays():
    """Test that empty preference arrays result in no filtering."""
    job = Mock(spec=JobOffer)
    job.location = "Paris"
    job.contract_type = ContractType.CDI
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []
    prefs.preferred_contract_types = []
    prefs.remote_preference = None
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


def test_passes_user_preferences_default_preferences_no_filtering():
    """Test that default preferences (remote=False, empty arrays) do not filter jobs."""
    job = Mock(spec=JobOffer)
    job.location = "Paris"  # Onsite job
    job.contract_type = ContractType.CDI
    
    prefs = Mock(spec=UserPreferences)
    prefs.preferred_locations = []  # Default
    prefs.preferred_contract_types = []  # Default
    prefs.remote_preference = False  # Default (changed from True to False)
    
    result = MatchingService.passes_user_preferences(job, prefs)
    assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
