import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_management.parsing_service import validate_email, validate_phone

def test_valid_email_formats():
    """Test that valid email formats are accepted."""
    valid_emails = [
        "test@example.com",
        "user.name@example.com",
        "user+tag@example.com",
        "user123@example.co.uk",
        "first.last@company.com",
    ]
    
    for email in valid_emails:
        assert validate_email(email), f"Email {email} should be valid"

def test_invalid_email_formats():
    """Test that invalid email formats are rejected."""
    invalid_emails = [
        "notanemail",
        "@example.com",
        "user@",
        "user@domain",
        "user..name@example.com",
        "user@.com",
        "user@domain.",
    ]
    
    for email in invalid_emails:
        assert not validate_email(email), f"Email {email} should be invalid"

def test_none_email_is_valid():
    """Test that None email is valid (optional field)."""
    assert validate_email(None), "None email should be valid"
    assert validate_email(""), "Empty email should be valid"
    assert validate_email("   "), "Whitespace-only email should be valid"

def test_valid_phone_formats():
    """Test that valid phone formats are accepted."""
    valid_phones = [
        "+33 6 12 34 56 78",  # French format
        "+1 (555) 123-4567",  # US format
        "06 12 34 56 78",  # French mobile without country code
        "+44 20 7946 0958",  # UK format
        "+49 30 1234567",  # German format
        "1234567890",  # Simple digits
        "+33123456789",  # No spaces
    ]
    
    for phone in valid_phones:
        assert validate_phone(phone), f"Phone {phone} should be valid"

def test_invalid_phone_formats():
    """Test that invalid phone formats are rejected."""
    invalid_phones = [
        "12345",  # Too short (less than 6 digits)
        "abc",  # No digits
        "+",  # Just plus sign
        "1234567890123456",  # Too long (more than 15 digits)
    ]
    
    for phone in invalid_phones:
        assert not validate_phone(phone), f"Phone {phone} should be invalid"

def test_none_phone_is_valid():
    """Test that None phone is valid (optional field)."""
    assert validate_phone(None), "None phone should be valid"
    assert validate_phone(""), "Empty phone should be valid"
    assert validate_phone("   "), "Whitespace-only phone should be valid"

def test_international_phone_formats():
    """Test that international phone formats are accepted."""
    international_phones = [
        "+852 1234 5678",  # Hong Kong
        "+81 90 1234 5678",  # Japan
        "+86 138 1234 5678",  # China
        "+91 98765 43210",  # India
        "+61 2 9876 5432",  # Australia
    ]
    
    for phone in international_phones:
        assert validate_phone(phone), f"International phone {phone} should be valid"

def test_email_with_whitespace():
    """Test that email with whitespace is handled correctly."""
    email = "  test@example.com  "
    assert validate_email(email), "Email with surrounding whitespace should be valid"

def test_phone_with_whitespace():
    """Test that phone with whitespace is handled correctly."""
    phone = "  +33 6 12 34 56 78  "
    assert validate_phone(phone), "Phone with surrounding whitespace should be valid"

def test_validation_functions_exist():
    """Test that validation functions are defined."""
    from cv_management.parsing_service import validate_email, validate_phone
    
    assert callable(validate_email), "validate_email should be a function"
    assert callable(validate_phone), "validate_phone should be a function"

def test_validation_in_parsing_service():
    """Test that validation is called in parsing_service."""
    from cv_management.parsing_service import parse_cv
    
    import inspect
    source = inspect.getsource(parse_cv)
    
    assert "validate_email" in source, "parse_cv should call validate_email"
    assert "validate_phone" in source, "parse_cv should call validate_phone"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
