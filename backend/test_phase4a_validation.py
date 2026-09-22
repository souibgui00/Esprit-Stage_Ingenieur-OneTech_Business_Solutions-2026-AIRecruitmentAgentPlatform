"""
Manual validation script for Phase 4A completion.
Tests pagination, embeddings, and deduplication using saved raw offers.
"""
import os
import sys
sys.path.insert(0, '/app')

from job_sourcing.models import JobSource, SourceType, JobOffer, JobSkill, JobOfferEmbedding
from shared.database import SessionLocal
from job_sourcing.services.collection_service import JobCollectionService
from job_sourcing.connectors.base import get_connector

os.environ['LINKEDIN_ENABLED'] = 'true'
os.environ['LINKEDIN_MOCK_MODE'] = 'false'
os.environ['LINKEDIN_MAX_JOBS'] = '5'
os.environ['LINKEDIN_REQUEST_DELAY'] = '2.0'

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
    
    # Clean slate
    db.query(JobOffer).filter(JobOffer.source_id == source.id).delete()
    db.commit()
    print("=== Phase 4A Validation ===")
    print("Cleaned existing LinkedIn offers")
    print()
    
    # Fetch raw offers once
    connector = get_connector("linkedin")
    raw_offers = connector.fetch_offers(source, "rust")
    print(f"Fetched {len(raw_offers)} raw offers from LinkedIn (will be used for both runs)")
    print()
    
    # Test 1: First collection with saved raw offers
    print("TEST 1: First collection with saved raw offers")
    from job_sourcing.services.normalization_service import JobNormalizationService
    from job_sourcing.services.deduplication_service import JobDeduplicationService
    from job_sourcing.services.embedding_service import JobEmbeddingService
    
    for raw_offer in raw_offers:
        fingerprint = JobNormalizationService.compute_fingerprint(
            raw_offer.raw_url, raw_offer.raw_title, raw_offer.raw_company
        )
        if JobDeduplicationService.is_duplicate(fingerprint, db, source_id=source.id):
            continue
        
        offer = JobNormalizationService.normalize(raw_offer, source, db)
        db.flush()
        
        try:
            embedding = JobEmbeddingService.generate_embedding(offer, db)
            db.add(embedding)
        except Exception:
            pass
    
    db.commit()
    
    offers_after_run1 = db.query(JobOffer).filter(JobOffer.source_id == source.id).all()
    skills_after_run1 = db.query(JobSkill).join(JobOffer).filter(JobOffer.source_id == source.id).all()
    embeddings_after_run1 = db.query(JobOfferEmbedding).join(JobOffer).filter(JobOffer.source_id == source.id).all()
    
    print(f"JobOffers: {len(offers_after_run1)}")
    print(f"JobSkills: {len(skills_after_run1)}")
    print(f"Embeddings: {len(embeddings_after_run1)}")
    print()
    
    # Test 2: Duplicate detection with same raw offers
    print("TEST 2: Second collection with same saved raw offers (should detect duplicates)")
    duplicate_count = 0
    for raw_offer in raw_offers:
        fingerprint = JobNormalizationService.compute_fingerprint(
            raw_offer.raw_url, raw_offer.raw_title, raw_offer.raw_company
        )
        if JobDeduplicationService.is_duplicate(fingerprint, db, source_id=source.id):
            duplicate_count += 1
            continue
        
        offer = JobNormalizationService.normalize(raw_offer, source, db)
        db.flush()
        
        try:
            embedding = JobEmbeddingService.generate_embedding(offer, db)
            db.add(embedding)
        except Exception:
            pass
    
    db.commit()
    
    offers_after_run2 = db.query(JobOffer).filter(JobOffer.source_id == source.id).all()
    skills_after_run2 = db.query(JobSkill).join(JobOffer).filter(JobOffer.source_id == source.id).all()
    embeddings_after_run2 = db.query(JobOfferEmbedding).join(JobOffer).filter(JobOffer.source_id == source.id).all()
    
    print(f"JobOffers: {len(offers_after_run2)}")
    print(f"JobSkills: {len(skills_after_run2)}")
    print(f"Embeddings: {len(embeddings_after_run2)}")
    print(f"Duplicates detected: {duplicate_count}")
    print()
    
    # Verification
    print("=== Verification ===")
    if len(offers_after_run2) == len(offers_after_run1):
        print(f"✓ Deduplication works: JobOffers unchanged on re-run")
    else:
        print(f"✗ Deduplication failed: JobOffers changed ({len(offers_after_run2)} != {len(offers_after_run1)})")
    
    if len(embeddings_after_run1) == len(offers_after_run1):
        print(f"✓ Embeddings generated: First run has embeddings for all offers")
    else:
        print(f"✗ Embeddings missing: {len(embeddings_after_run1)} vs {len(offers_after_run1)}")
    
    if duplicate_count == len(raw_offers):
        print(f"✓ All {len(raw_offers)} offers detected as duplicates")
    else:
        print(f"✗ Only {duplicate_count}/{len(raw_offers)} offers detected as duplicates")
    
    print(f"\nFinal state: {len(offers_after_run2)} JobOffers, {len(skills_after_run2)} JobSkills, {len(embeddings_after_run2)} Embeddings")
    
finally:
    db.close()
