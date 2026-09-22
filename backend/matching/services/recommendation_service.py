"""
RecommendationService - Thin orchestration layer above MatchingService.

This service wraps the existing MatchingService to provide recommendation-level
semantics without duplicating the matching logic. It reuses the existing Match model
and MatchingService.compute_match/get_best_matches_for_cv.
"""
import logging
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

import sys
sys.path.insert(0, '/app')

from matching.models import Match, MatchingConfig
from matching.matching_service import MatchingService
from matching.adapters.cosine_similarity_calculator import IEmbeddingSimilarityCalculator
from matching.adapters.groq_matching_evaluator import ILLMMatchingEvaluator
from job_sourcing.models import JobOffer

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Service that sits above MatchingService to provide recommendation-level semantics.
    
    Does NOT duplicate semantic or LLM scoring - simply orchestrates MatchingService
    and adds recommendation-level classification.
    """
    
    @staticmethod
    def get_recommendation_level(compatibility_score: float, threshold: float = 70.0) -> str:
        """
        Derive recommendation level from compatibility score and threshold.
        
        Args:
            compatibility_score: Combined compatibility score (0-100)
            threshold: Recommendation threshold (default 70)
            
        Returns:
            Recommendation level string
        """
        if compatibility_score >= 80:
            return "HIGHLY_RECOMMENDED"
        elif compatibility_score >= threshold:
            return "RECOMMENDED"
        elif compatibility_score >= 60:
            return "CONSIDER"
        else:
            return "NOT_RECOMMENDED"
    
    @staticmethod
    def get_recommendations_for_cv(
        cv_id: str,
        user_id: str,
        similarity_calculator: IEmbeddingSimilarityCalculator,
        llm_evaluator: ILLMMatchingEvaluator,
        db: Session,
        limit: int = 10,
        offset: int = 0
    ) -> List[Tuple[Match, dict]]:
        """
        Get ranked recommendations for a CV.
        
        This is a thin wrapper around MatchingService.get_best_matches_for_cv
        that adds recommendation-level classification.
        
        Args:
            cv_id: CV UUID
            user_id: User UUID
            similarity_calculator: Vector similarity calculator
            llm_evaluator: LLM matching evaluator
            db: Database session
            limit: Number of recommendations to return
            offset: Pagination offset
            
        Returns:
            List of (Match, job_offer_dict) tuples with recommendation metadata
        """
        # Use default recommendation threshold of 70.0
        # The 6-factor scoring uses fixed weights, so no user-configurable threshold is needed
        threshold = 70.0
        
        # Call existing MatchingService - this does all the heavy lifting
        ranked_pairs = MatchingService.get_best_matches_for_cv(
            cv_id=cv_id,
            user_id=user_id,
            similarity_calculator=similarity_calculator,
            llm_evaluator=llm_evaluator,
            db=db,
            limit=limit,
            offset=offset
        )
        
        # Add recommendation-level metadata to each match
        recommendations = []
        for match, job_offer in ranked_pairs:
            # Derive recommendation level
            recommendation_level = RecommendationService.get_recommendation_level(
                match.compatibility_score,
                threshold
            )
            
            # Build job offer dict (same as matching router)
            job_offer_dict = {
                "id": str(job_offer.id),
                "title": job_offer.title,
                "company": job_offer.company,
                "location": job_offer.location,
                "source_url": job_offer.source_url,
                "contract_type": job_offer.contract_type.value if job_offer.contract_type else None,
                "posted_at": job_offer.posted_at.isoformat() if job_offer.posted_at else None,
            }
            
            # Add recommendation metadata to match
            match_dict = {
                "id": str(match.id),
                "cv_id": str(match.cv_id),
                "job_offer_id": str(match.job_offer_id),
                "semantic_similarity": match.semantic_similarity,
                "llm_score": match.llm_score,
                "compatibility_score": match.compatibility_score,
                "matching_points": match.matching_points or [],
                "gap_points": match.gap_points or [],
                "summary": match.summary,
                "recommendation_level": recommendation_level,
                "computed_at": match.computed_at.isoformat() if match.computed_at else None
            }
            
            recommendations.append((match_dict, job_offer_dict))
        
        logger.info(f"Generated {len(recommendations)} recommendations for CV {cv_id}")
        return recommendations
    
    @staticmethod
    def get_recommendation_reasons(match: Match) -> dict:
        """
        Extract recommendation reasons from existing Match data.
        
        Reuses matching_points and gap_points from the Match model.
        
        Args:
            match: Match object
            
        Returns:
            Dictionary with recommendation reasons
        """
        return {
            "matching_points": match.matching_points or [],
            "gap_points": match.gap_points or [],
            "summary": match.summary,
            "important_matched_skills": [p for p in (match.matching_points or []) if isinstance(p, str)],
            "important_missing_skills": [g for g in (match.gap_points or []) if isinstance(g, str)]
        }
