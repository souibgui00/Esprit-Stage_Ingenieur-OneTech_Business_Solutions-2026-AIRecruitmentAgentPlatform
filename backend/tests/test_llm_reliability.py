import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_management.adapters.groq_llm_extractor import GroqLLMExtractor

def test_llm_extractor_has_retry_logic():
    """Test that LLM extractor has retry configuration."""
    extractor = GroqLLMExtractor()
    
    assert extractor.max_retries == 2, "Should have 2 max retries"
    assert extractor.timeout == 30, "Should have 30 second timeout"

def test_llm_extractor_has_system_prompt():
    """Test that LLM extractor uses a system prompt."""
    extractor = GroqLLMExtractor()
    
    # Check that system prompt is defined in the method
    import inspect
    source = inspect.getsource(extractor.extract_structured_data)
    
    assert "system_prompt" in source, "Should define system prompt"
    assert "system" in source, "Should use system role in messages"

def test_valid_json_parsing():
    """Test that valid JSON is parsed correctly."""
    extractor = GroqLLMExtractor()
    
    valid_json = '{"full_name": "Test User", "email": "test@example.com"}'
    result = json.loads(valid_json)
    
    assert result["full_name"] == "Test User"
    assert result["email"] == "test@example.com"

def test_invalid_json_raises_error():
    """Test that invalid JSON raises an error."""
    extractor = GroqLLMExtractor()
    
    invalid_json = '{"full_name": "Test User", "email": "test@example.com"'  # Missing closing brace
    
    with pytest.raises(json.JSONDecodeError):
        json.loads(invalid_json)

def test_retry_on_json_decode_error():
    """Test that retry mechanism works on JSON decode errors."""
    extractor = GroqLLMExtractor()
    
    # Mock the Groq client
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '{"full_name": "Test"}'
    
    # First call returns invalid JSON, second call returns valid JSON
    call_count = [0]
    def mock_create(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return Mock(choices=[Mock(message=Mock(content='{"invalid": json'))])
        else:
            return mock_response
    
    mock_client.chat.completions.create = mock_create
    extractor.client = mock_client
    
    # Should succeed on second attempt
    result = extractor.extract_structured_data("test text")
    
    assert call_count[0] == 2, "Should retry once"
    assert result["full_name"] == "Test"

def test_retry_exhaustion_raises_error():
    """Test that exhausting retries raises an error."""
    extractor = GroqLLMExtractor()
    
    # Mock the Groq client to always return invalid JSON
    mock_client = Mock()
    mock_client.chat.completions.create = Mock(
        return_value=Mock(choices=[Mock(message=Mock(content='{"invalid": json'))])
    )
    extractor.client = mock_client
    
    # Should raise ValueError after exhausting retries
    with pytest.raises(ValueError) as exc_info:
        extractor.extract_structured_data("test text")
    
    assert "invalid JSON" in str(exc_info.value)
    assert "2 attempts" in str(exc_info.value)

def test_timeout_configuration():
    """Test that timeout is passed to the LLM call."""
    extractor = GroqLLMExtractor()
    
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '{"full_name": "Test"}'
    
    mock_client.chat.completions.create = Mock(return_value=mock_response)
    extractor.client = mock_client
    
    extractor.extract_structured_data("test text")
    
    # Verify timeout was passed
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert "timeout" in call_kwargs
    assert call_kwargs["timeout"] == 30

def test_system_prompt_content():
    """Test that system prompt contains expected instructions."""
    extractor = GroqLLMExtractor()
    
    import inspect
    source = inspect.getsource(extractor.extract_structured_data)
    
    # Check for key system prompt elements
    assert "expert" in source.lower(), "System prompt should mention expertise"
    assert "json" in source.lower(), "System prompt should mention JSON"
    assert "structure" in source.lower(), "System prompt should mention structure"

def test_pydantic_validation_preserved():
    """Test that Pydantic validation is still in place in parsing_service."""
    from cv_management.parsing_service import parse_cv
    from cv_management.schemas import ParsedCVData
    
    import inspect
    source = inspect.getsource(parse_cv)
    
    assert "ParsedCVData" in source, "Should use Pydantic ParsedCVData for validation"

def test_retry_only_on_llm_call():
    """Test that retry logic is isolated to LLM extraction, not entire parsing."""
    from cv_management.parsing_service import parse_cv
    
    import inspect
    source = inspect.getsource(parse_cv)
    
    # The retry logic should be in the LLM extractor, not in parse_cv
    assert "retry" not in source.lower(), "parse_cv should not have retry logic"
    assert "max_retries" not in source.lower(), "parse_cv should not have retry configuration"

def test_llm_messages_structure():
    """Test that LLM call uses both system and user messages."""
    extractor = GroqLLMExtractor()
    
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '{"full_name": "Test"}'
    
    mock_client.chat.completions.create = Mock(return_value=mock_response)
    extractor.client = mock_client
    
    extractor.extract_structured_data("test text")
    
    # Verify messages structure
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    messages = call_kwargs["messages"]
    
    assert len(messages) == 2, "Should have 2 messages (system + user)"
    assert messages[0]["role"] == "system", "First message should be system"
    assert messages[1]["role"] == "user", "Second message should be user"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
