"""
Simple fresh collection test.
"""
import os
import sys
sys.path.insert(0, '/app')

from job_sourcing.models import JobSource, SourceType, JobOffer, JobOfferEmbedding
from shared.database import SessionLocal
from job_sourcing.services.collection_service import JobCollectionService

os.environ['LINKEDIN_ENABLED'] = 'true'
os.environ['LINKEDIN_MOCK_MODE'] = 'false'
os.environ['LINKEDIN_MAX_JOBS'] = '2'
os.environ['LINKEDIN_REQUEST_DELAY'] = '1.0'

db = SessionLocal()
try:
    source = db.query(JobSource).filter(JobSource.name == "linkedin").first()
    if not source:
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        db.add(source)
        db.commit()
    
    # Delete all existing offers
    db.query(JobOffer).filter(JobOffer.source_id == source.id).delete()
    db.commit()
    print("Cleaned existing offers")
    
    print("\n=== Collection: 'golang' ===")
    run = JobCollectionService.run_collection(source, "golang", db)
    
    print(f"Status: {run.status}")
    print(f"Collected: {run.offers_collected}")
    print(f"Error: {run.error_message}")
    
    offers = db.query(JobOffer).filter(JobOffer.source_id == source.id).all()
    embeddings = db.query(JobOfferEmbedding).join(JobOffer).filter(JobOffer.source_id == source.id).all()
    
    print(f"\nOffers: {len(offers)}")
    print(f"Embeddings: {len(embeddings)}")
    
    for offer in offers:
        emb = db.query(JobOfferEmbedding).filter(JobOfferEmbedding.job_offer_id == offer.id).first()
        print(f"  {offer.title}: {'✓' if emb else '✗'} embedding")
    
finally:
    db.close()
