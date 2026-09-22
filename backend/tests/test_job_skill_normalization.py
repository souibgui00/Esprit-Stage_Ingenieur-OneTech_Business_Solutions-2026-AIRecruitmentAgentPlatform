import pytest
import uuid
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from shared.database import SessionLocal, engine
from job_sourcing.models import JobSource, JobOffer, JobSkill, SourceType
from job_sourcing.connectors.base import JobOfferDTO
from job_sourcing.services.normalization_service import JobNormalizationService
from cv_management.skill_normalization import normalize_skill_name, categorize_skill, normalize_skill
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


def test_job_skill_normalization():
    """Test that job skills are normalized using the same logic as CV skills."""
    db = SessionLocal()
    
    try:
        # Test normalization function
        assert normalize_skill_name("Python") == "python"
        assert normalize_skill_name("py") == "python"
        assert normalize_skill_name("ReactJS") == "react.js"
        assert normalize_skill_name("C++") == "c++"
        assert normalize_skill_name("Docker") == "docker"
        
    finally:
        db.close()


def test_job_skill_aliases():
    """Test that job skill aliases work the same as CV skill aliases."""
    db = SessionLocal()
    
    try:
        # Test aliases
        assert normalize_skill_name("js") == "javascript"
        assert normalize_skill_name("ts") == "typescript"
        assert normalize_skill_name("nodejs") == "node.js"
        assert normalize_skill_name("postgres") == "postgresql"
        
    finally:
        db.close()


def test_job_skill_special_skills():
    """Test that special technical skills are preserved."""
    db = SessionLocal()
    
    try:
        # Test special skills preservation
        assert normalize_skill_name("C++") == "c++"
        assert normalize_skill_name("C#") == "c#"
        assert normalize_skill_name(".NET") == ".net"
        assert normalize_skill_name("Node.js") == "node.js"
        assert normalize_skill_name("React.js") == "react.js"
        
    finally:
        db.close()


def test_job_skill_categories():
    """Test that job skills have categories like CV skills."""
    db = SessionLocal()
    
    try:
        # Test categories
        assert categorize_skill("python") == "programming_language"
        assert categorize_skill("react") == "framework"
        assert categorize_skill("postgresql") == "database"
        assert categorize_skill("docker") == "devops"
        assert categorize_skill("aws") == "cloud"
        
    finally:
        db.close()


def test_job_skill_reuse_no_duplicates():
    """Test that the same skill is reused, not duplicated in Skills table."""
    db = SessionLocal()
    
    try:
        # Normalize same skill twice
        skill1 = normalize_skill("Python", db)
        skill2 = normalize_skill("py", db)
        
        # Should return the same skill object
        assert skill1.id == skill2.id
        assert skill1.canonical_name == skill2.canonical_name == "python"
        
        # Verify only one skill in database
        skills = db.query(Skill).filter_by(canonical_name="python").all()
        assert len(skills) == 1
        
    finally:
        db.close()


def test_job_skill_creation():
    """Test that JobSkill records are created during normalization."""
    db = SessionLocal()
    
    try:
        # Create a source
        source = JobSource(
            name="Test Source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        # Create a DTO with skills
        dto = JobOfferDTO(
            raw_title="Python Developer",
            raw_company="Test Company",
            raw_location="Paris",
            raw_description="We need Python, Django, and Docker skills.",
            raw_url="https://example.com/job/test-job-skill-creation"
        )
        
        # Normalize (should create JobSkill records)
        offer = JobNormalizationService.normalize(dto, source, db)
        db.commit()
        db.refresh(offer)
        
        # Verify JobSkill records were created
        job_skills = db.query(JobSkill).filter_by(job_offer_id=offer.id).all()
        assert len(job_skills) > 0, "JobSkill records should be created"
        
        # Verify skills are canonical
        for job_skill in job_skills:
            skill = db.query(Skill).filter_by(id=job_skill.skill_id).first()
            assert skill is not None
            assert skill.canonical_name == skill.canonical_name.lower()  # Should be lowercase except special skills
        
    finally:
        db.close()


def test_job_skill_essential_nice_to_have():
    """Test that JobSkill importance field works."""
    db = SessionLocal()
    
    try:
        # Create a source and offer
        source = JobSource(
            name="Test Source",
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
            raw_description="Python skills required.",
            raw_url="https://example.com/job/test-essential-nice-to-have"
        )
        
        offer = JobNormalizationService.normalize(dto, source, db)
        db.commit()
        db.refresh(offer)
        
        # Verify importance is set to 'essential' (default)
        job_skills = db.query(JobSkill).filter_by(job_offer_id=offer.id).all()
        for job_skill in job_skills:
            assert job_skill.importance == "essential"
        
    finally:
        db.close()


def test_job_skill_cascade_on_offer_delete():
    """Test that deleting a JobOffer cascades to JobSkill records."""
    db = SessionLocal()
    
    try:
        # Create source and offer
        source = JobSource(
            name="Test Source",
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
            raw_description="Python skills required.",
            raw_url="https://example.com/job/cascade-test"
        )
        
        offer = JobNormalizationService.normalize(dto, source, db)
        db.commit()
        db.refresh(offer)
        
        # Store IDs
        offer_id = offer.id
        job_skill_ids = [js.id for js in db.query(JobSkill).filter_by(job_offer_id=offer_id).all()]
        
        # Delete offer
        db.delete(offer)
        db.commit()
        
        # Verify JobSkill records were cascade deleted
        for job_skill_id in job_skill_ids:
            assert db.query(JobSkill).filter_by(id=job_skill_id).first() is None
        
    finally:
        # Cleanup
        db.rollback()
        db.close()


def test_job_skill_duplicate_prevention():
    """Test that duplicate JobSkill records are prevented by unique constraint."""
    db = SessionLocal()
    
    try:
        # Create source and offer
        source = JobSource(
            name="Test Source",
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
            raw_description="Python and Python skills required.",
            raw_url="https://example.com/job/test-duplicate-prevention"
        )
        
        offer = JobNormalizationService.normalize(dto, source, db)
        db.commit()
        db.refresh(offer)
        
        # Count JobSkill records
        job_skills = db.query(JobSkill).filter_by(job_offer_id=offer.id).all()
        
        # Should not have duplicates (same skill normalized once)
        skill_names = [db.query(Skill).filter_by(id=js.skill_id).first().canonical_name for js in job_skills]
        assert len(skill_names) == len(set(skill_names)), "Should not have duplicate skills"
        
    finally:
        db.close()


def test_cv_job_skill_consistency():
    """Test that CV and Job skills use the same canonical names."""
    db = SessionLocal()
    
    try:
        # Normalize "Python" for CV
        cv_skill = normalize_skill("Python", db)
        
        # Normalize "py" for Job (should get same canonical skill)
        job_skill = normalize_skill("py", db)
        
        # Should be the same skill
        assert cv_skill.id == job_skill.id
        assert cv_skill.canonical_name == job_skill.canonical_name == "python"
        
    finally:
        db.close()


def test_job_skill_table_exists():
    """Test that job_skills table exists with correct schema."""
    db = SessionLocal()
    
    try:
        # Check table exists
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'job_skills'
            )
        """)).fetchone()
        
        assert result[0] is True, "job_skills table should exist"
        
        # Check columns
        result = db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'job_skills'
            ORDER BY ordinal_position
        """)).fetchall()
        
        columns = {row[0]: row[1] for row in result}
        assert "id" in columns
        assert "job_offer_id" in columns
        assert "skill_id" in columns
        assert "importance" in columns
        assert "created_at" in columns
        
    finally:
        db.close()


def test_job_skill_unique_constraint():
    """Test that unique constraint on (job_offer_id, skill_id) exists."""
    db = SessionLocal()
    
    try:
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'uq_job_offer_skill'
            )
        """)).fetchone()
        
        assert result[0] is True, "Unique constraint should exist"
        
    finally:
        db.close()


def test_required_skills_backward_compatibility():
    """Test that required_skills field is still populated for backward compatibility."""
    db = SessionLocal()
    
    try:
        # Create source and offer
        source = JobSource(
            name="Test Source",
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
            raw_description="Python and Django skills required.",
            raw_url="https://example.com/job/test-backward-compatibility"
        )
        
        offer = JobNormalizationService.normalize(dto, source, db)
        db.commit()
        db.refresh(offer)
        
        # Verify required_skills field is still populated
        assert offer.required_skills is not None
        
        # Verify it's valid JSON
        skills = json.loads(offer.required_skills)
        assert isinstance(skills, list)
        
    finally:
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
