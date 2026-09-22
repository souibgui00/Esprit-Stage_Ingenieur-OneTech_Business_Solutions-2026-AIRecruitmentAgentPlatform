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
from cv_management.skill_normalization import normalize_skill
from cv_management.models import Skill


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data after each test without wiping real data."""
    yield
    db = SessionLocal()
    try:
        test_sources = db.query(JobSource).filter(JobSource.name == "Test Source").all()
        for ts in test_sources:
            db.delete(ts)
        db.commit()
    finally:
        db.close()


def test_matching_reads_canonical_job_skills():
    """Test that Matching service reads job skills from job_skills junction table."""
    db = SessionLocal()
    
    try:
        # Create a job source and offer
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
            raw_description="We need Python and Django skills.",
            raw_url="https://example.com/job/matching-test"
        )
        
        offer = JobNormalizationService.normalize(dto, source, db)
        db.commit()
        db.refresh(offer)
        
        # Verify job skills were created
        job_skills = db.query(JobSkill).filter_by(job_offer_id=offer.id).all()
        assert len(job_skills) > 0, "JobSkill records should be created"
        
        # Verify skills are canonical
        job_skill_names = []
        for job_skill in job_skills:
            skill = db.query(Skill).filter_by(id=job_skill.skill_id).first()
            job_skill_names.append(skill.canonical_name)
        
        # Should have canonical names like "python", "django"
        assert "python" in job_skill_names
        assert "django" in job_skill_names
        
        # Verify MatchingService can read these skills
        # (We don't need to call the full matching logic, just verify the query works)
        job_skills_from_db = (
            db.query(Skill.canonical_name)
            .join(JobSkill, JobSkill.skill_id == Skill.id)
            .filter(JobSkill.job_offer_id == offer.id)
            .all()
        )
        
        req_skills_list = [s[0] for s in job_skills_from_db]
        assert len(req_skills_list) > 0
        assert "python" in req_skills_list
        assert "django" in req_skills_list
        
    finally:
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
