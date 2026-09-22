"""
Test LinkedIn real collection end-to-end.
This script performs a real collection from LinkedIn without mock data.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import SessionLocal
from job_sourcing.models import JobSource, JobOffer, CollectionRun
from job_sourcing.services.collection_service import JobCollectionService

def test_linkedin_collection():
    """Test real LinkedIn collection."""
    db = SessionLocal()
    
    try:
        # Get LinkedIn source
        linkedin_source = db.query(JobSource).filter(JobSource.name == "linkedin").first()
        
        if not linkedin_source:
            print("❌ LinkedIn source not found in database")
            return False
        
        print(f"✓ Found LinkedIn source: {linkedin_source.name} (ID: {linkedin_source.id})")
        print(f"  Type: {linkedin_source.type}")
        print(f"  Base URL: {linkedin_source.base_url}")
        print(f"  Active: {linkedin_source.is_active}")
        
        # Clean up any existing test data
        print("\nCleaning up existing test data...")
        db.query(CollectionRun).filter(CollectionRun.source_id == linkedin_source.id).delete()
        db.query(JobOffer).filter(JobOffer.source_id == linkedin_source.id).delete()
        db.commit()
        
        # Perform collection
        keywords = "python"
        print(f"\n=== Starting LinkedIn Collection ===")
        print(f"Keywords: {keywords}")
        print(f"Note: This uses REAL LinkedIn guest API (not mock data)")
        
        start_time = time.time()
        run = JobCollectionService.run_collection(linkedin_source, keywords, db)
        duration = time.time() - start_time
        
        print(f"\n=== Collection Completed ===")
        print(f"Duration: {duration:.2f}s")
        print(f"Status: {run.status}")
        print(f"Offers collected: {run.offers_collected}")
        
        if run.error_message:
            print(f"Error: {run.error_message}")
        
        # Check collected offers
        offers = db.query(JobOffer).filter(JobOffer.source_id == linkedin_source.id).all()
        print(f"\n=== Collected Offers ===")
        print(f"Total offers in database: {len(offers)}")
        
        if offers:
            print("\nFirst offer details:")
            offer = offers[0]
            print(f"  Title: {offer.title}")
            print(f"  Company: {offer.company}")
            print(f"  Location: {offer.location}")
            print(f"  Source URL: {offer.source_url}")
            print(f"  Contract Type: {offer.contract_type}")
            print(f"  Posted At: {offer.posted_at}")
            print(f"  Collected At: {offer.collected_at}")
            print(f"  Status: {offer.status}")
            print(f"  Fingerprint: {offer.fingerprint[:40]}...")
            print(f"  Description length: {len(offer.description)} chars")
            print(f"  Required Skills: {offer.required_skills}")
            
            # Verify it's a real LinkedIn URL
            if "linkedin.com" in offer.source_url:
                print(f"\n✓ VERIFIED: Real LinkedIn source URL")
            else:
                print(f"\n⚠ WARNING: Source URL does not appear to be from LinkedIn")
            
            # Check for embedding
            from job_sourcing.models import JobOfferEmbedding
            embedding = db.query(JobOfferEmbedding).filter(JobOfferEmbedding.job_offer_id == offer.id).first()
            if embedding:
                print(f"✓ VERIFIED: Embedding generated (vector length: {len(embedding.vector)})")
            else:
                print(f"⚠ WARNING: No embedding found for offer")
            
            # Show a few more offers
            if len(offers) > 1:
                print(f"\nAdditional offers (titles only):")
                for i, o in enumerate(offers[1:min(6, len(offers))], 1):
                    print(f"  {i}. {o.title} at {o.company}")
        
        return run.status.value == "SUCCESS" and len(offers) > 0
        
    except Exception as e:
        print(f"\n❌ Collection failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=== LinkedIn Real Collection Test ===\n")
    success = test_linkedin_collection()
    
    if success:
        print("\n✅ LinkedIn collection test PASSED")
        sys.exit(0)
    else:
        print("\n❌ LinkedIn collection test FAILED")
        sys.exit(1)
