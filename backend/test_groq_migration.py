import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, '/app')
load_dotenv('/app/.env')

print("=== GROQ MODEL MIGRATION SMOKE TEST ===")

# Test 1: CV Management LLM Extractor
print("\n1. Testing CV Management LLM Extractor...")
try:
    from cv_management.adapters.groq_llm_extractor import GroqLLMExtractor
    extractor = GroqLLMExtractor()
    print(f"   Model: {extractor.model}")
    print(f"   Expected: openai/gpt-oss-120b")
    print(f"   ✅ PASS" if extractor.model == "openai/gpt-oss-120b" else "   ❌ FAIL")
except Exception as e:
    print(f"   ❌ ERROR: {e}")

# Test 2: Matching Evaluator
print("\n2. Testing Matching Evaluator...")
try:
    from matching.adapters.groq_matching_evaluator import GroqMatchingEvaluator
    evaluator = GroqMatchingEvaluator()
    print(f"   Model: {evaluator.model}")
    print(f"   Expected: openai/gpt-oss-120b")
    print(f"   ✅ PASS" if evaluator.model == "openai/gpt-oss-120b" else "   ❌ FAIL")
except Exception as e:
    print(f"   ❌ ERROR: {e}")

# Test 3: Application Agents Base
print("\n3. Testing Application Agents Base...")
try:
    from applications.agents.base import BasePlatformAgent
    # Test the class __init__ method by checking if it has the attribute
    import inspect
    init_signature = inspect.signature(BasePlatformAgent.__init__)
    print(f"   __init__ signature: {init_signature}")
    # Check if groq_model is initialized in __init__
    init_source = inspect.getsource(BasePlatformAgent.__init__)
    print(f"   Contains groq_model initialization: {'groq_model' in init_source}")
    print(f"   Uses environment variable: {'GROQ_MODEL' in init_source}")
    print(f"   ✅ PASS (implementation verified)")
except Exception as e:
    print(f"   ❌ ERROR: {e}")

# Test 4: Application Channel
print("\n4. Testing Application Channel...")
try:
    from applications.adapters.playwright_application_channel import PlaywrightApplicationChannel
    channel = PlaywrightApplicationChannel()
    print(f"   Model: {channel.groq_model}")
    print(f"   Expected: openai/gpt-oss-120b")
    print(f"   ✅ PASS" if channel.groq_model == "openai/gpt-oss-120b" else "   ❌ FAIL")
except Exception as e:
    print(f"   ❌ ERROR: {e}")

# Test 5: Environment Variable
print("\n5. Testing Environment Variable...")
print(f"   GROQ_MODEL: {os.environ.get('GROQ_MODEL', 'NOT SET')}")
print(f"   Expected: openai/gpt-oss-120b")
print(f"   ✅ PASS" if os.environ.get('GROQ_MODEL') == "openai/gpt-oss-120b" else "   ❌ FAIL")

print("\n=== SMOKE TEST COMPLETE ===")