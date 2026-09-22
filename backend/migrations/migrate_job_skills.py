"""
Migration script to migrate existing job offers to job_skills junction table.
This script parses existing required_skills JSON and creates JobSkill records
using cv_management.skill_normalization for canonical skill names.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from shared.database import SessionLocal
from job_sourcing.models import JobOffer, JobSkill
from cv_management.skill_normalization import normalize_skill
from cv_management.models import Skill


def migrate_job_skills():
    """Migrate existing job offers to job_skills junction table."""
    db = SessionLocal()
    
    try:
        # Get all job offers with required_skills
        offers = db.query(JobOffer).filter(JobOffer.required_skills.isnot(None)).all()
        
        migrated_offers = 0
        migrated_skills = 0
        skipped_duplicates = 0
        failed_skills = 0
        
        for offer in offers:
            try:
                # Parse required_skills JSON
                if not offer.required_skills or offer.required_skills.strip() == "":
                    continue
                
                raw_skills = json.loads(offer.required_skills)
                if not isinstance(raw_skills, list):
                    # If not a list, try to split by comma
                    raw_skills = [s.strip() for s in offer.required_skills.split(',') if s.strip()]
                
                offer_skills_created = 0
                for raw_skill in raw_skills:
                    if not raw_skill or str(raw_skill).strip() == "":
                        continue
                    
                    # Normalize the skill
                    try:
                        skill = normalize_skill(str(raw_skill), db)
                        
                        # Check if JobSkill already exists
                        existing = db.query(JobSkill).filter_by(
                            job_offer_id=offer.id,
                            skill_id=skill.id
                        ).first()
                        
                        if existing:
                            skipped_duplicates += 1
                        else:
                            # Create JobSkill record
                            job_skill = JobSkill(
                                job_offer_id=offer.id,
                                skill_id=skill.id,
                                importance="essential"
                            )
                            db.add(job_skill)
                            offer_skills_created += 1
                            migrated_skills += 1
                    except Exception as e:
                        print(f"Failed to normalize skill '{raw_skill}' for offer {offer.id}: {e}")
                        failed_skills += 1
                
                if offer_skills_created > 0:
                    migrated_offers += 1
                    db.commit()
            
            except json.JSONDecodeError as e:
                print(f"Failed to parse required_skills for offer {offer.id}: {e}")
                continue
            except Exception as e:
                print(f"Failed to migrate offer {offer.id}: {e}")
                db.rollback()
                continue
        
        db.commit()
        
        print("=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Total offers processed: {len(offers)}")
        print(f"Offers migrated: {migrated_offers}")
        print(f"Skills migrated: {migrated_skills}")
        print(f"Skipped duplicates: {skipped_duplicates}")
        print(f"Failed skills: {failed_skills}")
        print("=" * 60)
        
        return migrated_offers, migrated_skills
    
    finally:
        db.close()


if __name__ == "__main__":
    migrate_job_skills()
