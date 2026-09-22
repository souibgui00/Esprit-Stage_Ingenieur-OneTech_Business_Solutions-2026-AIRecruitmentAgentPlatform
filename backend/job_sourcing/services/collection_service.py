from datetime import datetime
from sqlalchemy.orm import Session
import logging
import time

from job_sourcing.models import JobSource, CollectionRun, RunStatus, JobSkill, JobOffer
from job_sourcing.connectors.base import IJobConnector, get_connector
from job_sourcing.services.normalization_service import JobNormalizationService
from job_sourcing.services.deduplication_service import JobDeduplicationService
from job_sourcing.services.embedding_service import JobEmbeddingService
from matching.matching_service import MatchingService

logger = logging.getLogger(__name__)

class JobCollectionService:
    @staticmethod
    def run_collection(source: JobSource, keywords: str, db: Session) -> CollectionRun:
        """Run the end-to-end collection, normalization, deduplication and embedding pipeline."""
        start_time = time.time()
        logger.info(f"=== Collection Started ===")
        logger.info(f"Source: {source.name} (ID: {source.id})")
        logger.info(f"Keywords: {keywords}")
        
        run = CollectionRun(
            source_id=source.id,
            status=RunStatus.SUCCESS, # Will be set to SUCCESS/FAILED at the end
            offers_collected=0,
            started_at=datetime.utcnow()
        )
        db.add(run)
        db.commit()
        
        try:
            connector = get_connector(source.name)
            if not connector.is_available():
                raise RuntimeError(f"Connector for {source.name} is currently unavailable.")
                
            raw_offers = connector.fetch_offers(source, keywords)
            logger.info(f"Connector returned {len(raw_offers)} raw offers for keywords: {keywords}")
            
            # Distinguish between connector failure and empty results
            if not raw_offers:
                logger.info(f"No offers returned by connector for keywords: {keywords}")
                # Empty results is not a failure - just means no jobs found
            
            new_offers_count = 0
            duplicate_count = 0
            skills_created_count = 0
            embeddings_generated_count = 0
            embeddings_failed_count = 0
            
            for raw_offer in raw_offers:
                logger.info(f"Processing offer: {raw_offer.raw_title}")
                
                # 1. Check for duplicate source_url FIRST
                if raw_offer.raw_url and db.query(JobOffer.id).filter_by(source_url=raw_offer.raw_url).first():
                    duplicate_count += 1
                    logger.info(f"Duplicate source_url skipped: {raw_offer.raw_url}")
                    continue

                # 2. Check for duplicate fingerprint
                fingerprint = JobNormalizationService.compute_fingerprint(
                    raw_offer.raw_url,
                    raw_offer.raw_title,
                    raw_offer.raw_company
                )
                
                if JobDeduplicationService.is_duplicate(fingerprint, db, source_id=source.id):
                    duplicate_count += 1
                    logger.info(f"Duplicate detected: {raw_offer.raw_title}")
                    continue
                
                # 3. Normalize and embed in a savepoint (isolated per offer)
                try:
                    with db.begin_nested():
                        offer = JobNormalizationService.normalize(raw_offer, source, db)
                        db.flush()

                        # Generate embedding vector
                        try:
                            embedding = JobEmbeddingService.generate_embedding(offer, db)
                            db.add(embedding)
                            embeddings_generated_count += 1
                            logger.info(f"Embedding generated for offer: {offer.title}")
                        except Exception as emb_err:
                            embeddings_failed_count += 1
                            logger.error(f"Embedding failed for offer '{offer.title}': {emb_err}")
                    
                    new_offers_count += 1
                except Exception as offer_err:
                    logger.warning(f"Skipping offer '{raw_offer.raw_title}' due to error: {offer_err}")
                    continue
            
            duration = time.time() - start_time
            run.offers_collected = new_offers_count
            run.finished_at = datetime.utcnow()
            run.status = RunStatus.SUCCESS
            
            logger.info(f"=== Collection Completed Successfully ===")
            logger.info(f"Duration: {duration:.2f}s")
            logger.info(f"Raw offers retrieved: {len(raw_offers)}")
            logger.info(f"Duplicates skipped: {duplicate_count}")
            logger.info(f"New offers inserted: {new_offers_count}")
            logger.info(f"JobSkills created: {skills_created_count}")
            logger.info(f"Embeddings generated: {embeddings_generated_count}")
            logger.info(f"Embeddings failed: {embeddings_failed_count}")
            
            db.commit()
            
        except Exception as e:
            duration = time.time() - start_time
            db.rollback()
            # Reload run object after rollback and update its failure state
            db.add(run)
            run.finished_at = datetime.utcnow()
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            db.commit()
            
            logger.error(f"=== Collection Failed ===")
            logger.error(f"Duration: {duration:.2f}s")
            logger.error(f"Error: {e}", exc_info=True)
            
        return run
