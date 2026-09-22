import uuid
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_management.models import CVSkill, CVEmbedding, CV, CVStatus
from cv_management.adapters.pdf_text_extractor import (
    PdfTextExtractor,
    PDFExtractionError,
    PDFMalformedError,
    PDFEncryptedError,
    PDFScannedError
)
from cv_management.parsing_service import parse_cv
from cv_management.schemas import ParsedCVData, ExperienceData, EducationData
from sqlalchemy import inspect


def test_cv_skill_skill_id_has_cascade_in_orm():
    """Test that CVSkill.skill_id foreign key has CASCADE in ORM model."""
    from cv_management.models import CVSkill
    from sqlalchemy import ForeignKey
    
    # Get the skill_id column
    mapper = inspect(CVSkill)
    skill_id_column = mapper.columns['skill_id']
    
    # Check if it has ondelete="CASCADE"
    assert skill_id_column.foreign_keys, "skill_id should have a foreign key"
    for fk in skill_id_column.foreign_keys:
        assert fk.ondelete == "CASCADE", f"skill_id foreign key should have CASCADE, got {fk.ondelete}"


def test_pdf_extractor_normal_extraction():
    """Test that PDF extractor successfully extracts text from valid PDF."""
    extractor = PdfTextExtractor()
    
    # Create a minimal valid PDF for testing
    # We'll mock pdfplumber to avoid needing actual PDF files
    with patch('cv_management.adapters.pdf_text_extractor.pdfplumber') as mock_pdfplumber:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Sample CV text for a Python Developer with extensive experience"  # > 50 chars
        mock_pdf.pages = [mock_page]
        mock_pdf.is_encrypted = False
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        
        result = extractor.extract_text("test.pdf")
        
        assert "Sample CV text" in result
        assert "Python Developer" in result


def test_pdf_extractor_encrypted_pdf_raises_error():
    """Test that encrypted PDF raises PDFEncryptedError."""
    extractor = PdfTextExtractor()
    
    with patch('cv_management.adapters.pdf_text_extractor.pdfplumber') as mock_pdfplumber:
        # Simulate pdfplumber raising an exception for encrypted PDF
        mock_pdfplumber.open.side_effect = Exception("password required")
        
        with pytest.raises(PDFEncryptedError) as exc_info:
            extractor.extract_text("encrypted.pdf")
        
        assert "password-protected" in str(exc_info.value).lower()


def test_pdf_extractor_malformed_pdf_raises_error():
    """Test that malformed PDF raises PDFMalformedError."""
    extractor = PdfTextExtractor()
    
    with patch('cv_management.adapters.pdf_text_extractor.pdfplumber') as mock_pdfplumber:
        # Simulate a generic error with "syntax" in the message
        mock_pdfplumber.open.side_effect = Exception("PDF syntax error: Invalid structure")
        
        with pytest.raises(PDFMalformedError) as exc_info:
            extractor.extract_text("malformed.pdf")
        
        assert "malformed" in str(exc_info.value).lower() or "corrupted" in str(exc_info.value).lower()


def test_pdf_extractor_scanned_pdf_raises_error():
    """Test that scanned PDF (no extractable text) raises PDFScannedError."""
    extractor = PdfTextExtractor()
    
    with patch('cv_management.adapters.pdf_text_extractor.pdfplumber') as mock_pdfplumber:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""  # No text extracted
        mock_pdf.pages = [mock_page]
        mock_pdf.is_encrypted = False
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        
        with pytest.raises(PDFScannedError) as exc_info:
            extractor.extract_text("scanned.pdf")
        
        assert "scanned" in str(exc_info.value).lower() or "image-based" in str(exc_info.value).lower()


def test_pdf_extractor_very_little_text_raises_error():
    """Test that PDF with very little text (< 50 chars) raises PDFScannedError."""
    extractor = PdfTextExtractor()
    
    with patch('cv_management.adapters.pdf_text_extractor.pdfplumber') as mock_pdfplumber:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "ABC"  # Less than 50 chars
        mock_pdf.pages = [mock_page]
        mock_pdf.is_encrypted = False
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        
        with pytest.raises(PDFScannedError) as exc_info:
            extractor.extract_text("minimal.pdf")
        
        assert "scanned" in str(exc_info.value).lower() or "extractable text" in str(exc_info.value).lower()


def test_pdf_extractor_enough_text_succeeds():
    """Test that PDF with sufficient text (> 50 chars) succeeds."""
    extractor = PdfTextExtractor()
    
    with patch('cv_management.adapters.pdf_text_extractor.pdfplumber') as mock_pdfplumber:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is a valid CV with enough text to be considered not scanned. It has more than 50 characters."
        mock_pdf.pages = [mock_page]
        mock_pdf.is_encrypted = False
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        
        result = extractor.extract_text("valid.pdf")
        
        assert len(result.strip()) > 50
        assert "valid CV" in result


def test_parse_cv_regenerates_embedding():
    """Test that parse_cv deletes existing embedding and creates new one."""
    from cv_management.models import Skill
    from datetime import datetime, date
    
    # Create a mock CV
    cv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=user_id,
        filename="test.pdf",
        raw_file_url="/test.pdf",
        language="FR",
        status=CVStatus.UPLOADED
    )
    
    # Mock database session
    db = Mock()
    db.query.return_value.filter_by.return_value.first.return_value = None  # No existing embedding initially
    db.query.return_value.filter.return_value.first.return_value = None  # No existing skills
    
    # Mock text extractor
    text_extractor = Mock()
    text_extractor.extract_text.return_value = "John Doe\nPython Developer"
    
    # Mock LLM extractor
    llm_extractor = Mock()
    llm_extractor.extract_structured_data.return_value = {
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+33 6 12 34 56 78",
        "location": "Paris",
        "experiences": [
            {
                "title": "Developer",
                "company": "Tech Corp",
                "start_date": "2020-01-01",
                "end_date": None,
                "description": "Code",
                "is_current": True
            }
        ],
        "education": [],
        "skills": ["python"]
    }
    
    # Mock embedding provider
    embedding_provider = Mock()
    embedding_provider.embed.return_value = [0.1] * 1024
    
    # First parse - should create embedding
    parse_cv(cv, db, text_extractor, llm_extractor, embedding_provider)
    
    # Verify embedding was added
    embedding_add_calls = [call for call in db.add.call_args_list if isinstance(call[0][0], CVEmbedding)]
    assert len(embedding_add_calls) == 1, "Should have added one embedding"
    
    # Now simulate a reparse with existing embedding
    existing_embedding = Mock()
    db.query.return_value.filter_by.return_value.first.return_value = existing_embedding
    
    # Reset mocks
    db.add.reset_mock()
    db.delete.reset_mock()
    
    # Reparse - should delete old embedding and create new one
    parse_cv(cv, db, text_extractor, llm_extractor, embedding_provider)
    
    # Verify old embedding was deleted
    db.delete.assert_called_once_with(existing_embedding)
    
    # Verify new embedding was added
    embedding_add_calls = [call for call in db.add.call_args_list if isinstance(call[0][0], CVEmbedding)]
    assert len(embedding_add_calls) == 1, "Should have added one new embedding"


def test_parse_cv_handles_pdf_encrypted_error():
    """Test that parse_cv handles PDFEncryptedError with clear message."""
    from cv_management.models import CVStatus
    
    cv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=user_id,
        filename="encrypted.pdf",
        raw_file_url="/encrypted.pdf",
        language="FR",
        status=CVStatus.UPLOADED
    )
    
    db = Mock()
    text_extractor = Mock()
    text_extractor.extract_text.side_effect = PDFEncryptedError("PDF is password-protected")
    
    llm_extractor = Mock()
    embedding_provider = Mock()
    
    parse_cv(cv, db, text_extractor, llm_extractor, embedding_provider)
    
    # Verify CV was marked as failed
    assert cv.status == CVStatus.FAILED
    assert "password-protected" in cv.failure_reason.lower() or "pdf extraction failed" in cv.failure_reason.lower()


def test_parse_cv_handles_pdf_scanned_error():
    """Test that parse_cv handles PDFScannedError with clear message."""
    from cv_management.models import CVStatus
    
    cv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=user_id,
        filename="scanned.pdf",
        raw_file_url="/scanned.pdf",
        language="FR",
        status=CVStatus.UPLOADED
    )
    
    db = Mock()
    text_extractor = Mock()
    text_extractor.extract_text.side_effect = PDFScannedError("PDF appears to be scanned")
    
    llm_extractor = Mock()
    embedding_provider = Mock()
    
    parse_cv(cv, db, text_extractor, llm_extractor, embedding_provider)
    
    # Verify CV was marked as failed
    assert cv.status == CVStatus.FAILED
    assert "scanned" in cv.failure_reason.lower() or "pdf extraction failed" in cv.failure_reason.lower()


def test_parse_cv_handles_pdf_malformed_error():
    """Test that parse_cv handles PDFMalformedError with clear message."""
    from cv_management.models import CVStatus
    
    cv_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cv = CV(
        id=cv_id,
        user_id=user_id,
        filename="malformed.pdf",
        raw_file_url="/malformed.pdf",
        language="FR",
        status=CVStatus.UPLOADED
    )
    
    db = Mock()
    text_extractor = Mock()
    text_extractor.extract_text.side_effect = PDFMalformedError("PDF is malformed")
    
    llm_extractor = Mock()
    embedding_provider = Mock()
    
    parse_cv(cv, db, text_extractor, llm_extractor, embedding_provider)
    
    # Verify CV was marked as failed
    assert cv.status == CVStatus.FAILED
    assert "malformed" in cv.failure_reason.lower() or "pdf extraction failed" in cv.failure_reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
