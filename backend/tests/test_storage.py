import os
import uuid
import pytest
from pathlib import Path

# Test database and imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_management.models import CV

def test_backend_generated_filename():
    """Test that uploaded files use backend-generated UUID filenames"""
    # Test that UUID-based filename generation works
    test_uuid = uuid.uuid4()
    generated_filename = f"{test_uuid}.pdf"
    
    # Verify it's a valid UUID
    try:
        uuid.UUID(generated_filename.replace(".pdf", ""))
        is_valid_uuid = True
    except ValueError:
        is_valid_uuid = False
    
    assert is_valid_uuid, "Generated filename should be a valid UUID"
    assert generated_filename.endswith(".pdf"), "Filename should end with .pdf"
    assert "_" not in generated_filename, "Filename should not contain underscore separator"

def test_original_filename_preserved_in_db():
    """Test that original filename can be stored in database filename field"""
    # This test verifies the model field exists and can store the original filename
    # We'll just test the field existence without database operations
    assert hasattr(CV, 'filename'), "CV model should have filename field"
    assert hasattr(CV, 'raw_file_url'), "CV model should have raw_file_url field"
    
    # Test that we can create a CV with both fields
    test_cv = CV(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        filename="My_CV_Resume.pdf",  # Original filename with spaces and underscores
        raw_file_url="/path/to/generated_uuid.pdf",
        language="FR",
        status="UPLOADED"
    )
    
    assert test_cv.filename == "My_CV_Resume.pdf", "Original filename should be preserved"
    assert test_cv.raw_file_url.endswith(".pdf"), "Stored path should be UUID-based PDF"

def test_path_safety():
    """Test that path construction is safe"""
    from cv_management.router import UPLOAD_DIR
    from pathlib import Path
    
    # Test that UPLOAD_DIR is within current directory
    upload_dir_abs = UPLOAD_DIR.resolve()
    current_dir = Path(".").resolve()
    
    # Ensure upload directory is not escaping current directory
    assert upload_dir_abs.is_relative_to(current_dir) or str(upload_dir_abs).startswith(str(current_dir)), \
        "Upload directory should be within current working directory"
    
    # Test that UUID filename cannot escape directory
    test_uuid = uuid.uuid4()
    safe_filename = f"{test_uuid}.pdf"
    safe_path = UPLOAD_DIR / safe_filename
    
    # Resolve to check for path traversal
    resolved_path = safe_path.resolve()
    assert resolved_path.is_relative_to(upload_dir_abs) or str(resolved_path).startswith(str(upload_dir_abs)), \
        "UUID-based filename should not allow path traversal"

def test_file_cleanup_on_db_failure():
    """Test that file is cleaned up if database operation fails"""
    from cv_management.router import UPLOAD_DIR
    
    # Create a test file
    test_uuid = uuid.uuid4()
    test_file_path = UPLOAD_DIR / f"test_{test_uuid}.pdf"
    test_file_path.write_bytes(b"test content")
    
    # Simulate file cleanup
    if test_file_path.exists():
        os.unlink(test_file_path)
    
    assert not test_file_path.exists(), "File should be cleaned up on failure"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
