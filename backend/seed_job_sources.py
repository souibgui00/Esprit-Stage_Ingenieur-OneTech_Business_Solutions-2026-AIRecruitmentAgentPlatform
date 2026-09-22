"""
Seed default job sources into the database.
This script is idempotent - running it multiple times will not create duplicates.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from shared.database import engine
from job_sourcing.models import JobSource, SourceType

DEFAULT_SOURCES = [
    {
        "name": "linkedin",
        "type": SourceType.SCRAPER,
        "base_url": "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
        "is_active": True,
        "description": "LinkedIn public guest jobs API (scraper/guest endpoint - NOT official API)"
    },
    {
        "name": "remotive",
        "type": SourceType.OFFICIAL_API,
        "base_url": "https://remotive.com/api/remote-jobs",
        "is_active": True,
        "description": "Remotive official API for remote jobs"
    },
    {
        "name": "arbeitnow",
        "type": SourceType.OFFICIAL_API,
        "base_url": "https://www.arbeitnow.com/api/job-board-api",
        "is_active": True,
        "description": "Arbeitnow official API for remote jobs"
    },
    {
        "name": "jobicy",
        "type": SourceType.OFFICIAL_API,
        "base_url": "https://www.jobicy.com/api/jobs",
        "is_active": True,
        "description": "Jobicy official API for tech jobs"
    },
    {
        "name": "themuse",
        "type": SourceType.OFFICIAL_API,
        "base_url": "https://www.themuse.com/api/public/jobs",
        "is_active": True,
        "description": "TheMuse official API for jobs"
    },
    {
        "name": "bundesagentur",
        "type": SourceType.OFFICIAL_API,
        "base_url": "https://api.arbeitsagentur.de/jobsuche",
        "is_active": True,
        "description": "German Federal Employment Agency official API"
    },
    {
        "name": "welcometothejungle",
        "type": SourceType.SCRAPER,
        "base_url": "https://www.welcometothejungle.com/api/jobs",
        "is_active": True,
        "description": "WelcomeToTheJungle public Algolia search API (reverse-engineered)"
    }
]

def seed_job_sources():
    """Seed default job sources idempotently."""
    from sqlalchemy.orm import Session
    from shared.database import SessionLocal
    
    db = SessionLocal()
    try:
        created_count = 0
        skipped_count = 0
        
        for source_config in DEFAULT_SOURCES:
            # Check if source already exists
            existing = db.query(JobSource).filter(
                JobSource.name == source_config["name"]
            ).first()
            
            if existing:
                print(f"✓ Source '{source_config['name']}' already exists - skipping")
                skipped_count += 1
            else:
                source = JobSource(
                    name=source_config["name"],
                    type=source_config["type"],
                    base_url=source_config["base_url"],
                    is_active=source_config["is_active"]
                )
                db.add(source)
                db.commit()
                db.refresh(source)
                print(f"✓ Created source '{source_config['name']}' (ID: {source.id})")
                created_count += 1
        
        print(f"\n=== Summary ===")
        print(f"Created: {created_count}")
        print(f"Skipped (already exist): {skipped_count}")
        print(f"Total sources in database: {db.query(JobSource).count()}")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding job sources: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Seeding default job sources...")
    seed_job_sources()
    print("\nDone!")
