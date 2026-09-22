"""
Verify database consistency for LinkedIn jobs.
"""
import sys
sys.path.insert(0, '/app')

from job_sourcing.models import JobSource, JobOffer, JobSkill
from cv_management.models import Skill
from shared.database import SessionLocal

db = SessionLocal()
try:
    source = db.query(JobSource).filter(JobSource.name == "linkedin").first()
    if source:
        offers = db.query(JobOffer).filter(JobOffer.source_id == source.id).all()
        
        print(f"=== Database Consistency Report ===")
        print(f"Source: {source.name}")
        print(f"Source ID: {source.id}")
        print(f"Type: {source.type}")
        print(f"Base URL: {source.base_url}")
        print(f"Total JobOffers: {len(offers)}")
        print()
        
        for i, offer in enumerate(offers, 1):
            print(f"Job {i}:")
            print(f"  ID: {offer.id}")
            print(f"  Title: {offer.title}")
            print(f"  Company: {offer.company}")
            print(f"  Location: {offer.location}")
            print(f"  URL: {offer.source_url}")
            print(f"  Fingerprint: {offer.fingerprint}")
            print(f"  Description length: {len(offer.description)}")
            print(f"  Contract: {offer.contract_type}")
            print(f"  Posted: {offer.posted_at}")
            print(f"  Collected: {offer.collected_at}")
            print(f"  Status: {offer.status}")
            
            # Check JobSkills
            job_skills = db.query(JobSkill).filter(JobSkill.job_offer_id == offer.id).all()
            print(f"  JobSkills: {len(job_skills)}")
            for js in job_skills:
                skill = db.query(Skill).filter(Skill.id == js.skill_id).first()
                print(f"    - {skill.canonical_name} ({skill.category})")
            
            print()
        
        # Check for duplicates by fingerprint
        fingerprints = {}
        for offer in offers:
            if offer.fingerprint not in fingerprints:
                fingerprints[offer.fingerprint] = []
            fingerprints[offer.fingerprint].append(offer)
        
        duplicates = {fp: offers for fp, offers in fingerprints.items() if len(offers) > 1}
        if duplicates:
            print(f"⚠️  Found {len(duplicates)} duplicate fingerprints")
        else:
            print(f"✓ No duplicate fingerprints found")
    
finally:
    db.close()
