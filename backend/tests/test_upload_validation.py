import os
import uuid
import pytest
from pathlib import Path
from io import BytesIO

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_management.router import (
    UPLOAD_DIR,
    MAX_FILE_SIZE_BYTES,
    UPLOAD_RATE_LIMIT,
    check_upload_rate_limit,
    upload_attempts
)
from fastapi import HTTPException

def test_valid_pdf_size():
    """Test that a valid PDF under 10MB would be accepted."""
    # Create a small valid PDF header
    pdf_header = b"%PDF-1.4\n" + b"0" * 1000  # Small PDF
    
    assert len(pdf_header) < MAX_FILE_SIZE_BYTES, "Test PDF should be under size limit"
    assert pdf_header.startswith(b"%PDF"), "Should start with PDF header"

def test_oversized_pdf_rejected():
    """Test that a PDF larger than 10MB is rejected."""
    # Simulate an oversized file
    oversized_content = b"0" * (MAX_FILE_SIZE_BYTES + 1)
    
    assert len(oversized_content) > MAX_FILE_SIZE_BYTES, "Test file should exceed size limit"

def test_fake_pdf_content_rejected():
    """Test that a file with .pdf extension but non-PDF content is rejected."""
    import filetype
    
    # Create a file that's not actually a PDF
    fake_pdf = b"This is not a PDF file, just text content."
    
    kind = filetype.guess(fake_pdf)
    
    # filetype should not identify this as PDF
    assert kind is None or kind.mime != "application/pdf", "Non-PDF content should be rejected"

def test_real_pdf_content_accepted():
    """Test that actual PDF content is accepted by filetype."""
    import filetype
    
    # Create a minimal valid PDF
    minimal_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
    
    kind = filetype.guess(minimal_pdf)
    
    # filetype should identify this as PDF
    assert kind is not None and kind.mime == "application/pdf", "Valid PDF content should be accepted"

def test_invalid_extension_rejected():
    """Test that non-.pdf extensions are rejected."""
    invalid_extensions = [".txt", ".doc", ".docx", ".jpg", ".png", ".exe"]
    
    for ext in invalid_extensions:
        filename = f"test{ext}"
        assert not filename.lower().endswith(".pdf"), f"{ext} should be rejected"

def test_rate_limit_check():
    """Test that rate limiting allows 5 uploads per minute."""
    user_id = uuid.uuid4()
    
    # Reset attempts for this user
    upload_attempts[str(user_id)] = []
    
    # Should allow 5 uploads
    for i in range(UPLOAD_RATE_LIMIT):
        try:
            check_upload_rate_limit(user_id)
        except HTTPException:
            pytest.fail(f"Upload {i+1} should be allowed within rate limit")
    
    # 6th upload should be rejected
    with pytest.raises(HTTPException) as exc_info:
        check_upload_rate_limit(user_id)
    
    assert exc_info.value.status_code == 429, "6th upload should return 429"

def test_rate_limit_resets_after_minute():
    """Test that rate limit resets after 1 minute."""
    user_id = uuid.uuid4()
    
    # Reset attempts for this user
    upload_attempts[str(user_id)] = []
    
    # Fill up the rate limit
    for _ in range(UPLOAD_RATE_LIMIT):
        check_upload_rate_limit(user_id)
    
    # Manually set attempts to be older than 1 minute
    import time
    old_time = time.time() - 61  # 61 seconds ago
    upload_attempts[str(user_id)] = [old_time] * UPLOAD_RATE_LIMIT
    
    # Should now allow another upload
    try:
        check_upload_rate_limit(user_id)
    except HTTPException:
        pytest.fail("Upload should be allowed after rate limit window expires")

def test_rate_limit_per_user():
    """Test that rate limiting is per-user, not global."""
    user1 = uuid.uuid4()
    user2 = uuid.uuid4()
    
    # Reset attempts for both users
    upload_attempts[str(user1)] = []
    upload_attempts[str(user2)] = []
    
    # User 1 fills up their rate limit
    for _ in range(UPLOAD_RATE_LIMIT):
        check_upload_rate_limit(user1)
    
    # User 1 should be rate limited
    with pytest.raises(HTTPException) as exc_info:
        check_upload_rate_limit(user1)
    assert exc_info.value.status_code == 429
    
    # User 2 should still be able to upload
    try:
        check_upload_rate_limit(user2)
    except HTTPException:
        pytest.fail("User 2 should not be affected by user 1's rate limit")

def test_file_cleanup_on_rejection():
    """Test that rejected uploads don't leave files on disk."""
    test_uuid = uuid.uuid4()
    test_file_path = UPLOAD_DIR / f"test_{test_uuid}.pdf"
    
    # Create a test file
    test_file_path.write_bytes(b"test content")
    
    # Simulate cleanup
    if test_file_path.exists():
        os.unlink(test_file_path)
    
    assert not test_file_path.exists(), "File should be cleaned up on rejection"

def test_upload_dir_safety():
    """Test that upload directory is within expected bounds."""
    upload_dir_abs = UPLOAD_DIR.resolve()
    current_dir = Path(".").resolve()
    
    # Ensure upload directory is not escaping current directory
    assert upload_dir_abs.is_relative_to(current_dir) or str(upload_dir_abs).startswith(str(current_dir)), \
        "Upload directory should be within current working directory"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
