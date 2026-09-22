import os
import sys
sys.path.insert(0, '/app')
from dotenv import load_dotenv
load_dotenv('/app/.env')

print("=== GROQ JSON MODE RUNTIME TEST ===")

# Test CV Management LLM Extractor with actual Groq call
print("\nTesting CV Management LLM Extractor with Groq API...")
try:
    from cv_management.adapters.groq_llm_extractor import GroqLLMExtractor
    extractor = GroqLLMExtractor()
    
    # Simple test text
    test_cv_text = """John Doe
Email: john.doe@example.com
Phone: +1 234 567 890
Location: Paris, France

Experience:
Software Engineer at Tech Corp (2020-2023)
Python Developer at Startup Inc (2018-2020)

Skills: Python, JavaScript, React

Education:
Master in Computer Science at University of Paris (2018)"""
    
    result = extractor.extract_structured_data(test_cv_text)
    print(f"   Model used: {extractor.model}")
    print(f"   Result keys: {list(result.keys())}")
    print(f"   Full name extracted: {result.get('full_name', 'N/A')}")
    print(f"   Skills extracted: {result.get('skills', [])}")
    print(f"   ✅ PASS - Groq API call successful with JSON mode")
except Exception as e:
    print(f"   ❌ FAIL - Error: {e}")

print("\n=== RUNTIME TEST COMPLETE ===")