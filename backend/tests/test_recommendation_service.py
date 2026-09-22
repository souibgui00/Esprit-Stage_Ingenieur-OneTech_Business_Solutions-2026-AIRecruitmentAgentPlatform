"""
Tests for RecommendationService.
"""
import pytest
import uuid
from unittest.mock import Mock, MagicMock

import sys
sys.path.insert(0, '/app')

from matching.services.recommendation_service import RecommendationService
from matching.models import Match, MatchingConfig


def test_get_recommendation_level_highly_recommended():
    """Test recommendation level for scores >= 80."""
    level = RecommendationService.get_recommendation_level(85.0, 70.0)
    assert level == "HIGHLY_RECOMMENDED"
    
    level = RecommendationService.get_recommendation_level(80.0, 70.0)
    assert level == "HIGHLY_RECOMMENDED"


def test_get_recommendation_level_recommended():
    """Test recommendation level for scores >= threshold but < 80."""
    level = RecommendationService.get_recommendation_level(75.0, 70.0)
    assert level == "RECOMMENDED"
    
    level = RecommendationService.get_recommendation_level(70.0, 70.0)
    assert level == "RECOMMENDED"


def test_get_recommendation_level_consider():
    """Test recommendation level for scores >= 60 but < threshold."""
    level = RecommendationService.get_recommendation_level(65.0, 70.0)
    assert level == "CONSIDER"
    
    level = RecommendationService.get_recommendation_level(60.0, 70.0)
    assert level == "CONSIDER"


def test_get_recommendation_level_not_recommended():
    """Test recommendation level for scores < 60."""
    level = RecommendationService.get_recommendation_level(55.0, 70.0)
    assert level == "NOT_RECOMMENDED"
    
    level = RecommendationService.get_recommendation_level(0.0, 70.0)
    assert level == "NOT_RECOMMENDED"


def test_get_recommendation_level_custom_threshold():
    """Test recommendation level with custom threshold."""
    # Higher threshold
    level = RecommendationService.get_recommendation_level(75.0, 75.0)
    assert level == "RECOMMENDED"
    
    level = RecommendationService.get_recommendation_level(74.0, 75.0)
    assert level == "CONSIDER"
    
    # Lower threshold
    level = RecommendationService.get_recommendation_level(65.0, 60.0)
    assert level == "RECOMMENDED"


def test_get_recommendation_reasons():
    """Test extraction of recommendation reasons from Match."""
    match = Mock(spec=Match)
    match.matching_points = ["Python", "FastAPI", "PostgreSQL"]
    match.gap_points = ["AWS", "Kubernetes"]
    match.summary = "Strong backend match with some cloud skills gap"
    
    reasons = RecommendationService.get_recommendation_reasons(match)
    
    assert reasons["matching_points"] == ["Python", "FastAPI", "PostgreSQL"]
    assert reasons["gap_points"] == ["AWS", "Kubernetes"]
    assert reasons["summary"] == "Strong backend match with some cloud skills gap"
    assert reasons["important_matched_skills"] == ["Python", "FastAPI", "PostgreSQL"]
    assert reasons["important_missing_skills"] == ["AWS", "Kubernetes"]


def test_get_recommendation_reasons_empty():
    """Test recommendation reasons with empty match data."""
    match = Mock(spec=Match)
    match.matching_points = None
    match.gap_points = None
    match.summary = None
    
    reasons = RecommendationService.get_recommendation_reasons(match)
    
    assert reasons["matching_points"] == []
    assert reasons["gap_points"] == []
    assert reasons["summary"] is None
    assert reasons["important_matched_skills"] == []
    assert reasons["important_missing_skills"] == []


def test_get_recommendation_reasons_mixed_types():
    """Test recommendation reasons with mixed data types."""
    match = Mock(spec=Match)
    match.matching_points = ["Python", {"skill": "React"}, "SQL"]
    match.gap_points = ["AWS", {"gap": "Docker"}]
    match.summary = "Match with complex data"
    
    reasons = RecommendationService.get_recommendation_reasons(match)
    
    # Should only extract strings
    assert reasons["important_matched_skills"] == ["Python", "SQL"]
    assert reasons["important_missing_skills"] == ["AWS"]
    # Full lists should preserve all data
    assert len(reasons["matching_points"]) == 3
    assert len(reasons["gap_points"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
