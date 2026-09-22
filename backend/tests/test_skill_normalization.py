import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_management.skill_normalization import (
    normalize_skill_name,
    categorize_skill,
    SKILL_ALIASES,
    PRESERVE_FORMAT_SKILLS,
    SKILL_CATEGORIES
)

def test_case_normalization():
    """Test that skill names are normalized to lowercase where appropriate."""
    assert normalize_skill_name("Python") == "python"
    assert normalize_skill_name("JAVASCRIPT") == "javascript"
    assert normalize_skill_name("TypeScript") == "typescript"
    assert normalize_skill_name("Django") == "django"

def test_whitespace_normalization():
    """Test that whitespace is normalized."""
    assert normalize_skill_name("  python  ") == "python"
    assert normalize_skill_name("  javascript  ") == "javascript"
    assert normalize_skill_name("  django  ") == "django"

def test_common_aliases():
    """Test that common aliases are mapped correctly."""
    assert normalize_skill_name("JS") == "javascript"
    assert normalize_skill_name("js") == "javascript"
    assert normalize_skill_name("TS") == "typescript"
    assert normalize_skill_name("ts") == "typescript"
    assert normalize_skill_name("py") == "python"
    assert normalize_skill_name("ReactJS") == "react.js"
    assert normalize_skill_name("reactjs") == "react.js"
    assert normalize_skill_name("NodeJS") == "node.js"
    assert normalize_skill_name("nodejs") == "node.js"
    assert normalize_skill_name("VueJS") == "vue.js"
    assert normalize_skill_name("vuejs") == "vue.js"
    assert normalize_skill_name("postgres") == "postgresql"
    assert normalize_skill_name("mongo") == "mongodb"

def test_special_skills_preserved():
    """Test that special technical skills preserve their formatting."""
    assert normalize_skill_name("C++") == "c++"
    assert normalize_skill_name("c++") == "c++"
    assert normalize_skill_name("C#") == "c#"
    assert normalize_skill_name("c#") == "c#"
    assert normalize_skill_name(".NET") == ".net"
    assert normalize_skill_name(".net") == ".net"
    assert normalize_skill_name(".NET Core") == ".net core"
    assert normalize_skill_name("Node.js") == "node.js"
    assert normalize_skill_name("node.js") == "node.js"
    assert normalize_skill_name("React.js") == "react.js"
    assert normalize_skill_name("react.js") == "react.js"
    assert normalize_skill_name("Vue.js") == "vue.js"
    assert normalize_skill_name("vue.js") == "vue.js"
    assert normalize_skill_name("TypeScript") == "typescript"
    assert normalize_skill_name("PostgreSQL") == "postgresql"
    assert normalize_skill_name("MongoDB") == "mongodb"
    assert normalize_skill_name("Redis") == "redis"
    assert normalize_skill_name("AWS") == "aws"
    assert normalize_skill_name("Azure") == "azure"
    assert normalize_skill_name("GCP") == "gcp"

def test_unknown_skills():
    """Test that unknown skills are normalized but not aliased."""
    assert normalize_skill_name("Excel") == "excel"
    assert normalize_skill_name("PowerPoint") == "powerpoint"
    assert normalize_skill_name("Communication") == "communication"
    assert normalize_skill_name("Leadership") == "leadership"

def test_skill_categories():
    """Test that skills are categorized correctly."""
    assert categorize_skill("python") == "programming_language"
    assert categorize_skill("javascript") == "programming_language"
    assert categorize_skill("c++") == "programming_language"
    assert categorize_skill("c#") == "programming_language"
    assert categorize_skill("react") == "framework"
    assert categorize_skill("react.js") == "framework"
    assert categorize_skill("django") == "framework"
    assert categorize_skill("postgresql") == "database"
    assert categorize_skill("mysql") == "database"
    assert categorize_skill("mongodb") == "database"
    assert categorize_skill("aws") == "cloud"
    assert categorize_skill("docker") == "devops"
    assert categorize_skill("kubernetes") == "devops"
    assert categorize_skill("git") == "devops"
    assert categorize_skill("sql") == "other"
    assert categorize_skill("graphql") == "other"
    assert categorize_skill("unknownskill") == "other"

def test_deterministic_normalization():
    """Test that normalization is deterministic (same input = same output)."""
    skills = ["Python", "python", "PYTHON", "  python  ", "PyThOn"]
    results = [normalize_skill_name(skill) for skill in skills]
    
    # All should normalize to the same result
    assert len(set(results)) == 1, "Normalization should be deterministic"
    assert results[0] == "python"

def test_special_characters_removed():
    """Test that special characters are removed from non-preserved skills."""
    assert normalize_skill_name("Python!") == "python"
    assert normalize_skill_name("Java@") == "java"
    assert normalize_skill_name("C#") == "c#"  # Preserved
    assert normalize_skill_name("C++") == "c++"  # Preserved

def test_normalize_skill_integration():
    """Test that normalize_skill function works end-to-end."""
    from cv_management.skill_normalization import normalize_skill
    from cv_management.models import Skill
    from unittest.mock import Mock
    
    # Mock database session
    db = Mock()
    
    # Test skill doesn't exist
    db.query.return_value.filter.return_value.first.return_value = None
    db.flush.return_value = None
    
    skill = normalize_skill("Python", db)
    
    # Verify skill was created with normalized name
    assert skill.canonical_name == "python"
    assert skill.category == "programming_language"

def test_existing_skill_reused():
    """Test that existing skills are reused instead of creating duplicates."""
    from cv_management.skill_normalization import normalize_skill
    from cv_management.models import Skill
    from unittest.mock import Mock
    
    # Mock database session with existing skill
    db = Mock()
    existing_skill = Skill(canonical_name="python", category="programming_language")
    db.query.return_value.filter.return_value.first.return_value = existing_skill
    
    skill = normalize_skill("Python", db)
    
    # Verify existing skill was returned
    assert skill == existing_skill
    assert skill.canonical_name == "python"
    assert not db.add.called, "Should not add new skill if it exists"

def test_alias_dictionary_complete():
    """Test that alias dictionary is not empty."""
    assert len(SKILL_ALIASES) > 0, "Alias dictionary should not be empty"

def test_preserve_format_skills_defined():
    """Test that preserve format skills are defined."""
    assert "c++" in PRESERVE_FORMAT_SKILLS
    assert "c#" in PRESERVE_FORMAT_SKILLS
    assert ".net" in PRESERVE_FORMAT_SKILLS
    assert "node.js" in PRESERVE_FORMAT_SKILLS
    assert "react.js" in PRESERVE_FORMAT_SKILLS

def test_category_dictionary_complete():
    """Test that category dictionary is not empty."""
    assert len(SKILL_CATEGORIES) > 0, "Category dictionary should not be empty"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
