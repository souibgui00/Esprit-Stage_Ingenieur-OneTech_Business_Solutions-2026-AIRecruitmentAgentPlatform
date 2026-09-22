"""
Fresh LinkedIn collection test with detailed output.
"""
import os
import sys
sys.path.insert(0, '/app')

from job_sourcing.models import JobSource, SourceType, JobOffer, JobOfferEmbedding
from shared.database import SessionLocal
from job_sourcing.services.collection_service import JobCollectionService

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

os.environ['LINKEDIN_ENABLED'] = 'true'
os.environ['LINKEDIN_MOCK_MODE'] = 'false'
os.environ['LINKEDIN_MAX_JOBS'] = '2'
os.environ['LINKEDIN_REQUEST_DELAY'] = '1.0'

db = SessionLocal()
try:
    # Clean up existing LinkedIn data FIRST
    source = db.query(JobSource).filter(JobSource.name == "linkedin").first()
    if source:
        # Delete all LinkedIn offers (CASCADE will handle embeddings and skills)
        deleted = db.query(JobOffer).filter(JobOffer.source_id == source.id).delete()
        db.commit()
        print(f"Cleaned up {deleted} existing LinkedIn offers")
    else:
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        print("Created LinkedIn source")
    
    # Close and reopen session to ensure clean state
    db.close()
    db = SessionLocal()
    source = db.query(JobSource).filter(JobSource.name == "linkedin").first()
    
    print("\n=== Starting Fresh Collection ===")
    print("Keywords: 'rust'")
    print("Max jobs: 2")
    print()
    
    run = JobCollectionService.run_collection(source, "rust", db)
    
    print(f"\n=== Collection Results ===")
    print(f"Status: {run.status}")
    print(f"Collected: {run.offers_collected}")
    print(f"Error: {run.error_message}")
    
    # Check results
    offers = db.query(JobOffer).filter(JobOffer.source_id == source.id).all()
    print(f"\nTotal offers in DB: {len(offers)}")
    
    embeddings = db.query(JobOfferEmbedding).join(JobOffer).filter(JobOffer.source_id == source.id).all()
    print(f"Total embeddings in DB: {len(embeddings)}")
    
    for offer in offers:
        embedding = db.query(JobOfferEmbedding).filter(JobOfferEmbedding.job_offer_id == offer.id).first()
        has_emb = "✓" if embedding else "✗"
        print(f"{has_emb} {offer.title} (desc: {len(offer.description)} chars)")
    
finally:
    db.close()
