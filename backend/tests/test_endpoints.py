import uuid
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_management.router import get_cv_status, reparse_cv
from cv_management.models import CV, CVStatus
from fastapi import HTTPException

def test_get_cv_status_success():
    """Test that CV status endpoint returns correct information."""
    from cv_management.router import get_cv_status
    from cv_management.models import CV, CVStatus
    from datetime import datetime
    
    # Create a mock CV
    cv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=user_id,
        filename="test.pdf",
        raw_file_url="/test.pdf",
        language="FR",
        status=CVStatus.PARSED,
        created_at=datetime.utcnow(),
        parsed_at=datetime.utcnow()
    )
    
    # Mock database session
    db = Mock()
    db.get.return_value = cv
    
    # Mock current user
    current_user = Mock()
    current_user.id = user_id
    
    # Call the endpoint
    result = get_cv_status(cv_id, db, current_user)
    
    # Verify result
    assert result["cv_id"] == str(cv_id)
    assert result["status"] == "PARSED"
    assert result["created_at"] is not None
    assert result["parsed_at"] is not None
    assert result["failure_reason"] is None

def test_get_cv_status_not_found():
    """Test that CV status endpoint returns 404 for non-existent CV."""
    from cv_management.router import get_cv_status
    
    # Mock database session - CV not found
    db = Mock()
    db.get.return_value = None
    
    # Mock current user
    current_user = Mock()
    current_user.id = uuid.uuid4()
    
    # Call the endpoint - should raise 404
    with pytest.raises(HTTPException) as exc_info:
        get_cv_status(uuid.uuid4(), db, current_user)
    
    assert exc_info.value.status_code == 404
    assert "non trouvé" in str(exc_info.value.detail)

def test_get_cv_status_unauthorized():
    """Test that CV status endpoint returns 403 for wrong owner."""
    from cv_management.router import get_cv_status
    from cv_management.models import CV, CVStatus
    from datetime import datetime
    
    # Create a mock CV owned by different user
    cv_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=uuid.uuid4(),  # Different user
        filename="test.pdf",
        raw_file_url="/test.pdf",
        language="FR",
        status=CVStatus.PARSED
    )
    
    # Mock database session
    db = Mock()
    db.get.return_value = cv
    
    # Mock current user (different from CV owner)
    current_user = Mock()
    current_user.id = uuid.uuid4()
    
    # Call the endpoint - should raise 403
    with pytest.raises(HTTPException) as exc_info:
        get_cv_status(cv_id, db, current_user)
    
    assert exc_info.value.status_code == 403
    assert "non autorisé" in str(exc_info.value.detail)

def test_reparse_cv_success():
    """Test that reparse endpoint successfully re-parses a CV."""
    from cv_management.router import reparse_cv
    from cv_management.models import CV, CVStatus
    from datetime import datetime
    
    # Create a mock CV
    cv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=user_id,
        filename="test.pdf",
        raw_file_url="/test.pdf",
        language="FR",
        status=CVStatus.FAILED,
        failure_reason="Test error"
    )
    
    # Mock database session
    db = Mock()
    db.get.return_value = cv
    db.refresh.return_value = cv
    
    # Mock current user
    current_user = Mock()
    current_user.id = user_id
    
    # Mock Path.exists to return True
    with patch.object(Path, 'exists', return_value=True):
        # Mock parse_cv function
        with patch('cv_management.router.parse_cv') as mock_parse:
            mock_parse.return_value = cv
            
            # Mock _enrich_cv to return the CV
            with patch('cv_management.router._enrich_cv', return_value=cv):
                # Call the endpoint
                result = reparse_cv(cv_id, db, current_user)
                
                # Verify parse_cv was called
                mock_parse.assert_called_once()
                
                # Verify database refresh was called
                db.refresh.assert_called()

def test_reparse_cv_not_found():
    """Test that reparse endpoint returns 404 for non-existent CV."""
    from cv_management.router import reparse_cv
    
    # Mock database session - CV not found
    db = Mock()
    db.get.return_value = None
    
    # Mock current user
    current_user = Mock()
    current_user.id = uuid.uuid4()
    
    # Call the endpoint - should raise 404
    with pytest.raises(HTTPException) as exc_info:
        reparse_cv(uuid.uuid4(), db, current_user)
    
    assert exc_info.value.status_code == 404
    assert "non trouvé" in str(exc_info.value.detail)

def test_reparse_cv_unauthorized():
    """Test that reparse endpoint returns 403 for wrong owner."""
    from cv_management.router import reparse_cv
    from cv_management.models import CV, CVStatus
    
    # Create a mock CV owned by different user
    cv_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=uuid.uuid4(),  # Different user
        filename="test.pdf",
        raw_file_url="/test.pdf",
        language="FR",
        status=CVStatus.FAILED
    )
    
    # Mock database session
    db = Mock()
    db.get.return_value = cv
    
    # Mock current user (different from CV owner)
    current_user = Mock()
    current_user.id = uuid.uuid4()
    
    # Call the endpoint - should raise 403
    with pytest.raises(HTTPException) as exc_info:
        reparse_cv(cv_id, db, current_user)
    
    assert exc_info.value.status_code == 403
    assert "non autorisé" in str(exc_info.value.detail)

def test_reparse_cv_file_not_found():
    """Test that reparse endpoint returns 400 if file is missing."""
    from cv_management.router import reparse_cv
    from cv_management.models import CV, CVStatus
    from pathlib import Path
    
    # Create a mock CV with non-existent file
    cv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=user_id,
        filename="test.pdf",
        raw_file_url="/nonexistent/test.pdf",  # File doesn't exist
        language="FR",
        status=CVStatus.FAILED
    )
    
    # Mock database session
    db = Mock()
    db.get.return_value = cv
    
    # Mock current user
    current_user = Mock()
    current_user.id = user_id
    
    # Mock Path.exists to return False
    with patch.object(Path, 'exists', return_value=False):
        # Call the endpoint - should raise 400
        with pytest.raises(HTTPException) as exc_info:
            reparse_cv(cv_id, db, current_user)
        
        assert exc_info.value.status_code == 400
        assert "introuvable" in str(exc_info.value.detail)

def test_reparse_cv_failed_cv_allowed():
    """Test that reparse endpoint works for failed CVs."""
    from cv_management.router import reparse_cv
    from cv_management.models import CV, CVStatus
    
    # Create a mock failed CV
    cv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=user_id,
        filename="test.pdf",
        raw_file_url="/test.pdf",
        language="FR",
        status=CVStatus.FAILED,
        failure_reason="Previous parsing error"
    )
    
    # Mock database session
    db = Mock()
    db.get.return_value = cv
    db.refresh.return_value = cv
    
    # Mock current user
    current_user = Mock()
    current_user.id = user_id
    
    # Mock file existence
    with patch.object(Path, 'exists', return_value=True):
        # Mock parse_cv function
        with patch('cv_management.router.parse_cv') as mock_parse:
            mock_parse.return_value = cv
            
            # Mock _enrich_cv to return the CV
            with patch('cv_management.router._enrich_cv', return_value=cv):
                # Call the endpoint - should succeed
                result = reparse_cv(cv_id, db, current_user)
                
                # Verify parse_cv was called
                mock_parse.assert_called_once()

def test_endpoints_exist():
    """Test that the new endpoints are defined in the router."""
    from cv_management.router import router
    import inspect
    
    # Get all route definitions
    routes = [route for route in router.routes]
    
    # Check for status endpoint
    status_routes = [r for r in routes if "/{cv_id}/status" in r.path]
    assert len(status_routes) > 0, "Status endpoint should exist"
    
    # Check for reparse endpoint
    reparse_routes = [r for r in routes if "/{cv_id}/reparse" in r.path]
    assert len(reparse_routes) > 0, "Reparse endpoint should exist"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
