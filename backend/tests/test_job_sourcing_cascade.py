import pytest
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from shared.database import SessionLocal, engine
from job_sourcing.models import JobSource, JobOffer, JobOfferEmbedding, CollectionRun, SourceType
from cv_management.models import CV, CVStatus


def test_job_source_cascade_deletes_job_offers():
    """Test that deleting a JobSource cascades to JobOffers."""
    db = SessionLocal()
    
    try:
        # Create a JobSource
        source = JobSource(
            name="Test Source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        # Create a JobOffer linked to the source
        offer = JobOffer(
            source_id=source.id,
            source_url="https://example.com/job/cascade-offer-test",
            fingerprint="test-fingerprint-1",
            title="Test Job",
            company="Test Company",
            description="Test description"
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)
        
        # Store IDs before deletion
        source_id = source.id
        offer_id = offer.id
        
        # Verify offer exists
        assert db.query(JobOffer).filter_by(id=offer_id).first() is not None
        
        # Delete the source
        db.delete(source)
        db.commit()
        
        # Verify offer was cascade deleted
        assert db.query(JobOffer).filter_by(id=offer_id).first() is None
        
    finally:
        db.rollback()
        db.close()


def test_job_offer_cascade_deletes_embedding():
    """Test that deleting a JobOffer cascades to JobOfferEmbedding."""
    db = SessionLocal()
    
    try:
        # Create a JobSource and JobOffer
        source = JobSource(
            name="Test Source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        offer = JobOffer(
            source_id=source.id,
            source_url="https://example.com/job/cascade-embedding-test",
            fingerprint="test-fingerprint-2",
            title="Test Job",
            company="Test Company",
            description="Test description"
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)
        
        # Create an embedding linked to the offer
        embedding = JobOfferEmbedding(
            job_offer_id=offer.id,
            vector=[0.1] * 1024,
            model_name="test-model"
        )
        db.add(embedding)
        db.commit()
        db.refresh(embedding)
        
        # Store IDs before deletion
        offer_id = offer.id
        embedding_id = embedding.id
        
        # Verify embedding exists
        assert db.query(JobOfferEmbedding).filter_by(id=embedding_id).first() is not None
        
        # Delete the offer
        db.delete(offer)
        db.commit()
        
        # Verify embedding was cascade deleted
        assert db.query(JobOfferEmbedding).filter_by(id=embedding_id).first() is None
        
    finally:
        db.rollback()
        db.close()


def test_job_source_cascade_deletes_collection_runs():
    """Test that deleting a JobSource cascades to CollectionRuns."""
    db = SessionLocal()
    
    try:
        # Create a JobSource
        source = JobSource(
            name="Test Source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        # Create a CollectionRun linked to the source
        from job_sourcing.models import RunStatus
        run = CollectionRun(
            source_id=source.id,
            status=RunStatus.SUCCESS,
            offers_collected=5
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        # Store IDs before deletion
        source_id = source.id
        run_id = run.id
        
        # Verify run exists
        assert db.query(CollectionRun).filter_by(id=run_id).first() is not None
        
        # Delete the source
        db.delete(source)
        db.commit()
        
        # Verify run was cascade deleted
        assert db.query(CollectionRun).filter_by(id=run_id).first() is None
        
    finally:
        db.rollback()
        db.close()


def test_job_offer_deletion_cascade_chain():
    """Test that deleting a JobSource cascades through JobOffer to JobOfferEmbedding."""
    db = SessionLocal()
    
    try:
        # Create source -> offer -> embedding chain
        source = JobSource(
            name="Test Source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        offer = JobOffer(
            source_id=source.id,
            source_url="https://example.com/job/cascade-chain-test",
            fingerprint="test-fingerprint-3",
            title="Test Job",
            company="Test Company",
            description="Test description"
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)
        
        embedding = JobOfferEmbedding(
            job_offer_id=offer.id,
            vector=[0.1] * 1024,
            model_name="test-model"
        )
        db.add(embedding)
        db.commit()
        db.refresh(embedding)
        
        # Store IDs before deletion
        source_id = source.id
        offer_id = offer.id
        embedding_id = embedding.id
        
        # Delete source (should cascade through entire chain)
        db.delete(source)
        db.commit()
        
        # Verify entire chain is deleted
        assert db.query(JobSource).filter_by(id=source_id).first() is None
        assert db.query(JobOffer).filter_by(id=offer_id).first() is None
        assert db.query(JobOfferEmbedding).filter_by(id=embedding_id).first() is None
        
    finally:
        db.rollback()
        db.close()


def test_cascade_constraints_exist_in_database():
    """Test that CASCADE constraints are properly set in the database."""
    db = SessionLocal()
    
    try:
        # Check job_offers.source_id has CASCADE
        result = db.execute(text("""
            SELECT confdeltype 
            FROM pg_constraint 
            JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
            JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
            WHERE pg_namespace.nspname = 'public'
            AND pg_class.relname = 'job_offers'
            AND conname = 'job_offers_source_id_fkey'
        """)).fetchone()
        
        assert result is not None, "job_offers_source_id_fkey constraint not found"
        # confdeltype 'c' means CASCADE
        assert result[0] == 'c', "job_offers.source_id does not have CASCADE"
        
        # Check job_offer_embeddings.job_offer_id has CASCADE
        result = db.execute(text("""
            SELECT confdeltype 
            FROM pg_constraint 
            JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
            JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
            WHERE pg_namespace.nspname = 'public'
            AND pg_class.relname = 'job_offer_embeddings'
            AND conname = 'job_offer_embeddings_job_offer_id_fkey'
        """)).fetchone()
        
        assert result is not None, "job_offer_embeddings_job_offer_id_fkey constraint not found"
        assert result[0] == 'c', "job_offer_embeddings.job_offer_id does not have CASCADE"
        
        # Check collection_runs.source_id has CASCADE
        result = db.execute(text("""
            SELECT confdeltype 
            FROM pg_constraint 
            JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
            JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
            WHERE pg_namespace.nspname = 'public'
            AND pg_class.relname = 'collection_runs'
            AND conname = 'collection_runs_source_id_fkey'
        """)).fetchone()
        
        assert result is not None, "collection_runs_source_id_fkey constraint not found"
        assert result[0] == 'c', "collection_runs.source_id does not have CASCADE"
        
    finally:
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
