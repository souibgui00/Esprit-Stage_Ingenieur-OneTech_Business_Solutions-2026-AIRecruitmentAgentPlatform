"""
Backfill service for extracting certifications from existing job offers.

This service processes existing jobs to extract certifications using the new extraction logic,
normalize them, and update the structured certification fields.

This is separate from the migration to ensure clean separation of concerns.
"""
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from job_sourcing.models import JobOffer
from job_sourcing.services.normalization_service import JobNormalizationService
from shared.database import SessionLocal


class CertificationBackfillService:
    """Service for backfilling certification data for existing job offers."""
    
    @staticmethod
    def backfill_sample(db: Session, sample_size: int = 10) -> dict:
        """
        Backfill certification data for a sample of jobs for testing.
        
        Args:
            db: Database session
            sample_size: Number of jobs to process (default: 10)
        
        Returns:
            dict: Statistics about the backfill operation
        """
        print(f"Starting sample backfill ({sample_size} jobs)...")
        
        jobs = db.query(JobOffer).limit(sample_size).all()
        
        if not jobs:
            return {
                "total_jobs": 0,
                "processed": 0,
                "skipped": 0,
                "with_required": 0,
                "with_preferred": 0,
                "errors": 0
            }
        
        processed = 0
        skipped = 0
        with_required = 0
        with_preferred = 0
        errors = 0
        
        for job in jobs:
            try:
                # Extract certifications using the new logic
                required_certs, preferred_certs = JobNormalizationService.extract_certifications(
                    job.description, db
                )
                
                # Update job offer
                job.required_certifications = required_certs
                job.preferred_certifications = preferred_certs
                
                processed += 1
                if required_certs:
                    with_required += 1
                if preferred_certs:
                    with_preferred += 1
                
                print(f"  ✓ Processed: {job.title[:50]} (required: {len(required_certs)}, preferred: {len(preferred_certs)})")
                
            except Exception as e:
                errors += 1
                print(f"  ✗ Error processing {job.title[:50]}: {e}")
        
        db.commit()
        
        print(f"\nSample backfill complete:")
        print(f"  Total jobs: {len(jobs)}")
        print(f"  Processed: {processed}")
        print(f"  Skipped: {skipped}")
        print(f"  With required certifications: {with_required}")
        print(f"  With preferred certifications: {with_preferred}")
        print(f"  Errors: {errors}")
        
        return {
            "total_jobs": len(jobs),
            "processed": processed,
            "skipped": skipped,
            "with_required": with_required,
            "with_preferred": with_preferred,
            "errors": errors
        }
    
    @staticmethod
    def backfill_all(db: Session, limit: Optional[int] = None) -> dict:
        """
        Backfill certification data for all existing jobs.
        
        Args:
            db: Database session
            limit: Optional limit on number of jobs to process (None = all jobs)
        
        Returns:
            dict: Statistics about the backfill operation
        """
        print("Starting full backfill of all jobs...")
        
        query = db.query(JobOffer)
        if limit:
            query = query.limit(limit)
        
        jobs = query.all()
        
        if not jobs:
            return {
                "total_jobs": 0,
                "processed": 0,
                "skipped": 0,
                "with_required": 0,
                "with_preferred": 0,
                "errors": 0
            }
        
        print(f"Found {len(jobs)} jobs to process")
        
        processed = 0
        skipped = 0
        with_required = 0
        with_preferred = 0
        errors = 0
        
        for i, job in enumerate(jobs, 1):
            try:
                # Extract certifications using the new logic
                required_certs, preferred_certs = JobNormalizationService.extract_certifications(
                    job.description, db
                )
                
                # Update job offer
                job.required_certifications = required_certs
                job.preferred_certifications = preferred_certs
                
                processed += 1
                if required_certs:
                    with_required += 1
                if preferred_certs:
                    with_preferred += 1
                
                if i % 50 == 0:
                    print(f"  Progress: {i}/{len(jobs)} jobs processed...")
                
            except Exception as e:
                errors += 1
                print(f"  ✗ Error processing job {i} ({job.title[:40]}): {e}")
        
        db.commit()
        
        print(f"\nFull backfill complete:")
        print(f"  Total jobs: {len(jobs)}")
        print(f"  Processed: {processed}")
        print(f"  Skipped: {skipped}")
        print(f"  With required certifications: {with_required}")
        print(f"  With preferred certifications: {with_preferred}")
        print(f"  Errors: {errors}")
        
        return {
            "total_jobs": len(jobs),
            "processed": processed,
            "skipped": skipped,
            "with_required": with_required,
            "with_preferred": with_preferred,
            "errors": errors
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill certification data for existing jobs")
    parser.add_argument("--sample", action="store_true", help="Run sample backfill (10 jobs)")
    parser.add_argument("--sample-size", type=int, default=10, help="Sample size for sample backfill")
    parser.add_argument("--limit", type=int, help="Limit number of jobs to process")
    args = parser.parse_args()
    
    try:
        db = SessionLocal()
        
        if args.sample:
            results = CertificationBackfillService.backfill_sample(db, args.sample_size)
        else:
            results = CertificationBackfillService.backfill_all(db, args.limit)
        
        db.close()
        
        print("\n=== BACKFILL COMPLETE ===")
        print(f"Results: {results}")
        
    except Exception as e:
        print(f"Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
