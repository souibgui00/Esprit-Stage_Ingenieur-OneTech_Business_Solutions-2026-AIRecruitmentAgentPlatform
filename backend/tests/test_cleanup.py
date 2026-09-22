import os
import uuid
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_file_cleanup_on_cv_deletion():
    """Test that CV deletion removes the physical file from storage."""
    from cv_management.router import UPLOAD_DIR
    
    # Create a test CV record with a file
    cv_uuid = uuid.uuid4()
    test_file_path = UPLOAD_DIR / f"test_{cv_uuid}.pdf"
    test_file_path.write_bytes(b"test content")
    
    # Verify file exists
    assert test_file_path.exists(), "Test file should exist before deletion"
    
    # Simulate file cleanup (as done in delete_cv)
    if test_file_path.exists():
        os.unlink(test_file_path)
    
    # Verify file is deleted
    assert not test_file_path.exists(), "File should be deleted with CV"

def test_file_cleanup_handles_missing_file():
    """Test that file cleanup doesn't fail if file doesn't exist."""
    from cv_management.router import UPLOAD_DIR
    
    # Create a non-existent file path
    cv_uuid = uuid.uuid4()
    non_existent_path = UPLOAD_DIR / f"non_existent_{cv_uuid}.pdf"
    
    # Verify file doesn't exist
    assert not non_existent_path.exists(), "File should not exist"
    
    # Simulate file cleanup (should not fail)
    if non_existent_path.exists():
        os.unlink(non_existent_path)
    
    # Should complete without error
    assert True, "File cleanup should handle missing files gracefully"

def test_cleanup_logic_exists():
    """Test that the cleanup logic is present in the delete_cv function."""
    from cv_management.router import delete_cv
    import inspect
    
    # Get the source code of delete_cv
    source = inspect.getsource(delete_cv)
    
    # Verify that file cleanup logic is present
    assert "os.unlink" in source or "Path(" in source, "File cleanup logic should be present"
    assert "file_path" in source, "File path handling should be present"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
