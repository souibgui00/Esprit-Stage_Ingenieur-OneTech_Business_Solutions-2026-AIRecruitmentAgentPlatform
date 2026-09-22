from sqlalchemy.orm import Session
from job_sourcing.models import JobOffer
import uuid
import logging

logger = logging.getLogger(__name__)

class JobDeduplicationService:
    @staticmethod
    def is_duplicate(fingerprint: str, db: Session, source_id: uuid.UUID = None) -> bool:
        """
        Check if a job offer with the same fingerprint already exists in the database.
        
        Args:
            fingerprint: The job offer fingerprint to check
            db: Database session
            source_id: Optional source ID to limit deduplication to same source only
        
        Returns:
            True if duplicate exists, False otherwise
        """
        query = db.query(JobOffer).filter(JobOffer.fingerprint == fingerprint)
        if source_id:
            query = query.filter(JobOffer.source_id == source_id)
        
        existing = query.first()
        if existing:
            logger.debug(f"Duplicate found: fingerprint={fingerprint[:30]}..., source_id={source_id}")
        
        return existing is not None
