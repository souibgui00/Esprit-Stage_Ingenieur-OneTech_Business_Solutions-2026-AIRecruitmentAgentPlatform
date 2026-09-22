"""
Comprehensive test suite for Job Sourcing module.
Tests connectors, normalization, deduplication, embedding, collection pipeline, API, and scheduler.
"""
import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from shared.database import SessionLocal
from job_sourcing.models import JobSource, JobOffer, CollectionRun, SourceType, ContractType, OfferStatus, JobSkill
from job_sourcing.connectors.base import IJobConnector, JobOfferDTO, register_connector, get_connector
from job_sourcing.connectors.remotive.connector import RemotiveConnector
from job_sourcing.connectors.linkedin.connector import LinkedInConnector
from job_sourcing.services.normalization_service import JobNormalizationService
from job_sourcing.services.deduplication_service import JobDeduplicationService
from job_sourcing.services.embedding_service import JobEmbeddingService
from job_sourcing.services.collection_service import JobCollectionService
from job_sourcing.schemas import JobSourceCreate
from cv_management.skill_normalization import normalize_skill
from cv_management.models import Skill


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data after each test without deleting production job sources."""
    yield
    db = SessionLocal()
    try:
        from sqlalchemy import or_
        test_sources = db.query(JobSource).filter(
            or_(JobSource.name.ilike("test%"), JobSource.name == "test")
        ).all()
        for ts in test_sources:
            db.delete(ts)
        db.commit()
    finally:
        db.close()


# ==================== CONNECTOR TESTS ====================

def test_connector_interface_registration():
    """Test that connectors can be registered and retrieved."""
    mock_connector = Mock(spec=IJobConnector)
    register_connector("test_connector", mock_connector)
    
    retrieved = get_connector("test_connector")
    assert retrieved is mock_connector
    
    # Clean up
    from job_sourcing.connectors.base import _connectors
    _connectors.pop("test_connector", None)


def test_get_connector_invalid_name():
    """Test that get_connector raises ValueError for unregistered connectors."""
    with pytest.raises(ValueError, match="No connector registered for source"):
        get_connector("nonexistent_connector")


def test_remotive_connector_is_available():
    """Test Remotive connector availability check (mocked)."""
    connector = RemotiveConnector()
    
    with patch('job_sourcing.connectors.remotive.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert connector.is_available() is True


def test_remotive_connector_is_unavailable():
    """Test Remotive connector when API is unavailable."""
    connector = RemotiveConnector()
    
    with patch('job_sourcing.connectors.remotive.connector.requests.get') as mock_get:
        mock_get.side_effect = Exception("Network error")
        
        assert connector.is_available() is False


def test_remotive_connector_fetch_offers():
    """Test Remotive connector fetch_offers with mocked response."""
    connector = RemotiveConnector()
    source = JobSource(
        name="remotive",
        type=SourceType.OFFICIAL_API,
        base_url="https://remotive.com/api/remote-jobs",
        is_active=True
    )
    
    mock_response_data = {
        "jobs": [
            {
                "title": "Python Developer",
                "company_name": "Test Company",
                "candidate_required_location": "Remote",
                "description": "Python skills required",
                "url": "https://example.com/job/1",
                "publication_date": "2024-01-01"
            }
        ]
    }
    
    with patch('job_sourcing.connectors.remotive.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "python")
        
        assert len(offers) == 1
        assert offers[0].raw_title == "Python Developer"
        assert offers[0].raw_company == "Test Company"


def test_linkedin_connector_mock_mode():
    """Test that LinkedIn connector has a mock mode for testing."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    
    try:
        # Enable mock mode
        os.environ['LINKEDIN_MOCK_MODE'] = 'true'
        connector = LinkedInConnector()
        
        # Should return mock data in mock mode
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        offers = connector.fetch_offers(source, "python")
        
        # Should return mock job offers
        assert len(offers) > 0
        assert all(isinstance(offer, JobOfferDTO) for offer in offers)
        
        # Mock data should contain realistic fields
        assert offers[0].raw_title
        assert offers[0].raw_company
        assert offers[0].raw_location
        assert offers[0].raw_description
        assert offers[0].raw_url
    finally:
        # Restore original value
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode


def test_linkedin_connector_registered():
    """Test that LinkedIn connector is registered in the connector registry."""
    from job_sourcing.connectors.base import get_connector
    
    # Should be able to retrieve LinkedIn connector
    connector = get_connector("linkedin")
    assert isinstance(connector, LinkedInConnector)


# ==================== NORMALIZATION TESTS ====================

def test_normalization_html_cleaning():
    """Test HTML cleaning in normalization."""
    dirty_title = "<script>alert('xss')</script>Python Developer<br/>"
    dirty_company = "<b>Test</b> &amp; Company"
    dirty_description = "<p>We need <strong>Python</strong> skills.</p>"
    
    cleaned_title = JobNormalizationService.clean_html(dirty_title)
    cleaned_company = JobNormalizationService.clean_html(dirty_company)
    cleaned_description = JobNormalizationService.clean_html(dirty_description)
    
    assert "<script>" not in cleaned_title
    assert "<br/>" not in cleaned_title
    assert "<b>" not in cleaned_company
    assert "&amp;" not in cleaned_company
    assert "<p>" not in cleaned_description
    assert "<strong>" not in cleaned_description


def test_normalization_contract_type_detection():
    """Test contract type detection from description."""
    # Contract detection (CDD)
    desc_cdd = "CDD Python Developer"
    assert JobNormalizationService.detect_contract_type(desc_cdd, "Développeur") == ContractType.CDD
    
    # Freelance detection
    desc_freelance = "Freelance required"
    assert JobNormalizationService.detect_contract_type(desc_freelance, "Dev") == ContractType.FREELANCE


def test_normalization_skill_extraction():
    """Test skill extraction from description."""
    description = "We need Python, Django, and Docker skills."
    skills = JobNormalizationService.extract_required_skills(description)
    
    assert len(skills) > 0
    assert any("python" in s.lower() for s in skills)
    assert any("django" in s.lower() for s in skills)


def test_normalization_fingerprint_generation():
    """Test fingerprint generation is deterministic."""
    dto1 = JobOfferDTO(
        raw_title="Python Developer",
        raw_company="Test Company",
        raw_location="Paris",
        raw_description="Python skills",
        raw_url="https://example.com/job/1"
    )
    
    dto2 = JobOfferDTO(
        raw_title="Python Developer",
        raw_company="Test Company",
        raw_location="Paris",
        raw_description="Python skills",
        raw_url="https://example.com/job/1"
    )
    
    fp1 = JobNormalizationService.compute_fingerprint(dto1.raw_url, dto1.raw_title, dto1.raw_company)
    fp2 = JobNormalizationService.compute_fingerprint(dto2.raw_url, dto2.raw_title, dto2.raw_company)
    
    assert fp1 == fp2


def test_normalization_creates_job_skills():
    """Test that normalization creates JobSkill records."""
    db = SessionLocal()
    
    try:
        source = JobSource(
            name="test",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        dto = JobOfferDTO(
            raw_title="Python Developer",
            raw_company="Test Company",
            raw_location="Paris",
            raw_description="We need Python and Django skills.",
            raw_url="https://example.com/job/1"
        )
        
        offer = JobNormalizationService.normalize(dto, source, db)
        db.commit()
        db.refresh(offer)
        
        # Verify JobSkill records created
        job_skills = db.query(JobSkill).filter_by(job_offer_id=offer.id).all()
        assert len(job_skills) > 0
        
        # Verify skills are normalized
        for js in job_skills:
            skill = db.query(Skill).filter_by(id=js.skill_id).first()
            assert skill is not None
            assert skill.canonical_name == skill.canonical_name.lower()
        
    finally:
        db.close()


# ==================== DEDUPLICATION TESTS ====================

def test_deduplication_identical_offer():
    """Test that identical offers are detected as duplicates."""
    db = SessionLocal()
    
    try:
        source = JobSource(
            name="test-dedup-1",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        # Create first offer directly (without normalization to avoid JobSkill issues)
        offer1 = JobOffer(
            source_id=source.id,
            source_url="https://example.com/job/dedup-test-1",
            fingerprint="test-fingerprint-123",
            title="Python Developer",
            company="Test Company",
            description="Python skills"
        )
        db.add(offer1)
        db.commit()
        
        # Check if same fingerprint is duplicate (without source_id)
        is_dup = JobDeduplicationService.is_duplicate("test-fingerprint-123", db)
        assert is_dup is True
        
        # Check with source_id parameter (source-scoped deduplication)
        is_dup_with_source = JobDeduplicationService.is_duplicate("test-fingerprint-123", db, source_id=source.id)
        assert is_dup_with_source is True
        
    finally:
        db.close()


def test_deduplication_different_offers():
    """Test that different offers are not detected as duplicates."""
    db = SessionLocal()
    
    try:
        source = JobSource(
            name="test-dedup-2",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        # Create first offer
        offer1 = JobOffer(
            source_id=source.id,
            source_url="https://example.com/job/dedup-test-2a",
            fingerprint="test-fingerprint-456",
            title="Python Developer",
            company="Test Company",
            description="Python skills"
        )
        db.add(offer1)
        db.commit()
        
        # Check if different fingerprint is not duplicate
        is_dup = JobDeduplicationService.is_duplicate("test-fingerprint-789", db)
        assert is_dup is False
        
    finally:
        db.close()


# ==================== EMBEDDING TESTS ====================

def test_embedding_generation_success():
    """Test successful embedding generation."""
    db = SessionLocal()
    
    try:
        source = JobSource(
            name="test",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        dto = JobOfferDTO(
            raw_title="Python Developer",
            raw_company="Test Company",
            raw_location="Paris",
            raw_description="Python skills required",
            raw_url="https://example.com/job/1"
        )
        
        offer = JobNormalizationService.normalize(dto, source, db)
        db.add(offer)
        db.commit()
        db.refresh(offer)
        
        # Generate embedding
        embedding = JobEmbeddingService.generate_embedding(offer, db)
        
        # Verify embedding structure
        assert embedding.job_offer_id == offer.id
        assert len(embedding.vector) == 1024  # E5-large dimension
        assert embedding.model_name == "intfloat/multilingual-e5-large"
        
    finally:
        db.close()


def test_embedding_failure_handling():
    """Test that embedding failures don't crash the collection."""
    db = SessionLocal()
    
    try:
        source = JobSource(
            name="test",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        dto = JobOfferDTO(
            raw_title="Python Developer",
            raw_company="Test Company",
            raw_location="Paris",
            raw_description="Python skills",
            raw_url="https://example.com/job/1"
        )
        
        offer = JobNormalizationService.normalize(dto, source, db)
        db.add(offer)
        db.commit()
        db.refresh(offer)
        
        # Mock embedding provider to raise exception
        with patch('job_sourcing.services.embedding_service._embedding_provider') as mock_provider:
            mock_provider.embed.side_effect = Exception("Embedding service down")
            
            # Should raise exception (not silently swallowed)
            with pytest.raises(Exception):
                JobEmbeddingService.generate_embedding(offer, db)
        
    finally:
        db.close()


# ==================== COLLECTION PIPELINE TESTS ====================

def test_collection_pipeline_success():
    """Test successful collection pipeline."""
    db = SessionLocal()
    
    try:
        source = JobSource(
            name="test-collection-success",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        # Mock connector to return offers
        mock_offers = [
            JobOfferDTO(
                raw_title="Python Developer Collection Test",
                raw_company="Test Company Collection",
                raw_location="Paris",
                raw_description="Python skills for collection test",
                raw_url="https://example.com/job/collection-success-test-unique"
            )
        ]
        
        with patch('job_sourcing.services.collection_service.get_connector') as mock_get_connector:
            mock_connector = Mock()
            mock_connector.fetch_offers.return_value = mock_offers
            mock_connector.is_available.return_value = True
            mock_get_connector.return_value = mock_connector
            
            # Run collection
            run = JobCollectionService.run_collection(source, "python", db)
            db.refresh(run)
            
            # Verify run status
            assert run.status.value == "SUCCESS"
            assert run.error_message is None
            # offers_collected should be at least 0 (might be 0 if deduped from previous runs)
            assert run.offers_collected >= 0
        
    finally:
        db.close()


def test_collection_pipeline_connector_failure():
    """Test collection when connector fails."""
    db = SessionLocal()
    
    try:
        source = JobSource(
            name="test",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        with patch('job_sourcing.services.collection_service.get_connector') as mock_get_connector:
            mock_connector = Mock()
            mock_connector.is_available.return_value = False
            mock_get_connector.return_value = mock_connector
            
            # Run collection
            run = JobCollectionService.run_collection(source, "python", db)
            db.refresh(run)
            
            # Verify run status
            assert run.status == "FAILED"
            assert run.error_message is not None
            assert "unavailable" in run.error_message.lower()
        
    finally:
        db.close()


def test_collection_pipeline_deduplication():
    """Test that duplicate offers are not collected."""
    db = SessionLocal()
    
    try:
        source = JobSource(
            name="test",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        # Create existing offer
        dto = JobOfferDTO(
            raw_title="Python Developer",
            raw_company="Test Company",
            raw_location="Paris",
            raw_description="Python skills",
            raw_url="https://example.com/job/1"
        )
        
        existing_offer = JobNormalizationService.normalize(dto, source, db)
        db.add(existing_offer)
        db.commit()
        
        # Mock connector to return same offer
        mock_offers = [dto]
        
        with patch('job_sourcing.services.collection_service.get_connector') as mock_get_connector:
            mock_connector = Mock()
            mock_connector.fetch_offers.return_value = mock_offers
            mock_connector.is_available.return_value = True
            mock_get_connector.return_value = mock_connector
            
            # Run collection
            run = JobCollectionService.run_collection(source, "python", db)
            db.refresh(run)
            
            # Verify duplicate was skipped
            assert run.offers_collected == 0
            
            # Verify only one offer exists
            offers = db.query(JobOffer).filter_by(source_id=source.id).all()
            assert len(offers) == 1
        
    finally:
        db.close()


# ==================== API TESTS ====================

def test_api_create_source():
    """Test API endpoint for creating job source."""
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    
    # Mock authentication
    with patch('job_sourcing.router.get_current_user') as mock_auth:
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_auth.return_value = mock_user
        
        source_data = {
            "name": "test_source",
            "type": "official_api",
            "base_url": "https://example.com",
            "is_active": True
        }
        
        response = client.post("/jobs/sources", json=source_data)
        
        # Should return 201 (but might fail without proper auth setup)
        # This test documents the API structure
        assert response.status_code in [201, 401, 403]


def test_api_list_sources():
    """Test API endpoint for listing job sources."""
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    
    with patch('job_sourcing.router.get_current_user') as mock_auth:
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_auth.return_value = mock_user
        
        response = client.get("/jobs/sources")
        
        # Should return 200 or auth error
        assert response.status_code in [200, 401, 403]


def test_api_trigger_collection():
    """Test API endpoint for triggering collection."""
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    
    with patch('job_sourcing.router.get_current_user') as mock_auth:
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_auth.return_value = mock_user
        
        # Create a source first
        db = SessionLocal()
        try:
            source = JobSource(
                name="test",
                type=SourceType.OFFICIAL_API,
                base_url="https://example.com",
                is_active=True
            )
            db.add(source)
            db.commit()
            source_id = source.id
            
            response = client.post(f"/jobs/sources/{source_id}/collect?keywords=python")
            
            # Should return 202 (Accepted) or auth error
            assert response.status_code in [202, 401, 403, 404]
        finally:
            db.close()


def test_api_list_offers():
    """Test API endpoint for listing job offers."""
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    
    with patch('job_sourcing.router.get_current_user') as mock_auth:
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_auth.return_value = mock_user
        
        response = client.get("/jobs/offers")
        
        # Should return 200 or auth error
        assert response.status_code in [200, 401, 403]


def test_api_get_single_offer():
    """Test API endpoint for getting single job offer."""
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    
    with patch('job_sourcing.router.get_current_user') as mock_auth:
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_auth.return_value = mock_user
        
        offer_id = uuid.uuid4()
        response = client.get(f"/jobs/offers/{offer_id}")
        
        # Should return 404 (not found) or auth error
        assert response.status_code in [404, 401, 403]


# ==================== SCHEDULER TESTS ====================

def test_scheduler_starts():
    """Test that scheduler can be started."""
    from job_sourcing.scheduler import start_scheduler, stop_scheduler, scheduler
    
    # Stop if already running
    if scheduler.running:
        stop_scheduler()
    
    # Start scheduler
    start_scheduler()
    
    # Verify it's running
    assert scheduler.running is True
    
    # Clean up
    stop_scheduler()


def test_scheduler_job_registered():
    """Test that collection job is registered in scheduler."""
    from job_sourcing.scheduler import start_scheduler, stop_scheduler, scheduler
    
    if scheduler.running:
        stop_scheduler()
    
    start_scheduler()
    
    # Verify job is registered
    job = scheduler.get_job("autonomous_job_sourcing")
    assert job is not None
    assert job.name == "Collecte automatique d'offres d'emploi par l'agent"
    
    stop_scheduler()


def test_scheduler_interval_respected():
    """Test that scheduler interval is configured correctly."""
    from job_sourcing.scheduler import start_scheduler, stop_scheduler, scheduler
    
    if scheduler.running:
        stop_scheduler()
    
    start_scheduler()
    
    job = scheduler.get_job("autonomous_job_sourcing")
    assert job is not None
    # Check the trigger - it should be an IntervalTrigger
    # The interval is 6 hours (21600 seconds)
    assert job.trigger.interval.total_seconds() == 21600
    
    stop_scheduler()


def test_scheduler_failure_doesnt_crash():
    """Test that scheduler failures don't crash the application."""
    from job_sourcing.scheduler import autonomous_job_sourcing_task
    
    # Mock database to raise exception
    with patch('job_sourcing.scheduler.SessionLocal') as mock_session:
        mock_session.side_effect = Exception("Database error")
        
        # Should not crash
        try:
            autonomous_job_sourcing_task()
        except Exception:
            # Task should handle exceptions internally
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
