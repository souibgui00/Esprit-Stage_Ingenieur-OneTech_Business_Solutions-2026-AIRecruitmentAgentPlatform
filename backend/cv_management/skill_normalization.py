import re
from sqlalchemy.orm import Session

from cv_management.models import Skill


# Common skill aliases - map variants to canonical form
# Keys are lowercased raw input; values are canonical names stored in DB
SKILL_ALIASES = {
    # JavaScript / TypeScript
    "js": "javascript",
    "ts": "typescript",
    "ecmascript": "javascript",
    "es6": "javascript",
    "es2015": "javascript",

    # Python
    "py": "python",
    "python3": "python",

    # React variants → match CV canonical 'reactnextjs' if CV merged React+Next.js
    # But for new job skills we normalise to 'react' (distinct from 'nextjs')
    "react.js": "react",
    "reactjs": "react",
    "react native": "react native",
    # Next.js
    "next.js": "nextjs",
    "next": "nextjs",
    # CV stored 'reactnextjs' as a merged skill; keep it as-is via DB lookup
    # Job descriptions emit 'React' or 'Next.js'; we add both to resolve matches

    # Node / backend JS
    "node.js": "nodejs",
    "nodjs": "nodejs",
    "expressjs": "express",
    "express.js": "express",
    "nestjs": "nestjs",
    "nest.js": "nestjs",

    # Vue
    "vuejs": "vue",
    "vue.js": "vue",

    # Angular
    "angularjs": "angular",

    # Java ecosystem
    "spring boot": "spring boot",
    "springboot": "spring boot",
    "spring": "spring",
    "spring framework": "spring",

    # Python web frameworks
    "django rest framework": "django",
    "flask": "flask",
    "fastapi": "fastapi",
    "fast api": "fastapi",
    "symfony": "symfony",

    # Databases
    "postgres": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "mongoDB": "mongodb",
    "nosql": "nosql",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "redis": "redis",
    "elasticsearch": "elasticsearch",
    "pgvector": "pgvector",

    # Cloud
    "amazon web services": "aws",
    "amazon aws": "aws",
    "gcp": "gcp",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",

    # DevOps / CI
    "k8s": "kubernetes",
    "helm": "helm",
    "ci/cd": "cicd",
    "ci cd": "cicd",
    "github actions": "github actions",
    "gitlab ci": "gitlab ci",
    "jenkins": "jenkins",
    "docker": "docker",
    "docker hub": "docker hub",
    "sonarqube": "sonarqube",
    "prometheus": "prometheus",
    "grafana": "grafana",
    "nexus": "nexus",
    "git": "git",
    "github": "github",
    "gitlab": "gitlab",
    "terraform": "terraform",
    "ansible": "ansible",

    # ML / AI
    "machine learning": "machine learning",
    "ml": "machine learning",
    "deep learning": "deep learning",
    "dl": "deep learning",
    "artificial intelligence": "ai",
    "natural language processing": "nlp",
    "nlp": "nlp",
    "computer vision": "computer vision",
    "scikit learn": "scikitlearn",
    "scikit-learn": "scikitlearn",
    "sklearn": "scikitlearn",
    "scikitlearn": "scikitlearn",
    "sentence bert": "sentencebert",
    "sentence-bert": "sentencebert",
    "sbert": "sentencebert",
    "sentencebert": "sentencebert",
    "random forest": "random forest",
    "llm": "llms",
    "llms": "llms",
    "large language models": "llms",
    "rag": "rag",
    "retrieval augmented generation": "rag",
    "vector embeddings": "vector embeddings",
    "embeddings": "vector embeddings",

    # Methodologies
    "agile": "agile",
    "scrum": "scrum",
    "devops": "devops",
    "dev ops": "devops",
    "domain driven design": "domaindriven design",
    "ddd": "domaindriven design",
    "domain-driven design": "domaindriven design",

    # Other languages
    "c++": "c++",
    "c#": "c#",
    ".net": ".net",
    ".net core": ".net core",
    "dotnet": ".net",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "ruby": "ruby",
    "php": "php",
    "swift": "swift",
    "kotlin": "kotlin",
    "scala": "scala",
    "r": "r",

    # Web
    "html5": "html",
    "html": "html",
    "css3": "css",
    "css": "css",
    "sass": "sass",
    "scss": "sass",
    "graphql": "graphql",
    "rest api": "rest",
    "rest": "rest",
    "api": "api",

    # Data
    "data science": "data science",
    "sql": "sql",
    "javafx": "javafx",
    "aws": "aws",
    "azure": "azure",
    "kubernetes": "kubernetes",
}

# Skills that should preserve their special formatting
PRESERVE_FORMAT_SKILLS = {
    "c++",
    "c#",
    ".net",
    ".net core",
    "node.js",
    "react.js",
    "vue.js",
    "typescript",
    "postgresql",
    "mongodb",
    "redis",
    "aws",
    "azure",
    "gcp",
}

# Simple skill categories
SKILL_CATEGORIES = {
    # Programming languages
    "python": "programming_language",
    "javascript": "programming_language",
    "typescript": "programming_language",
    "java": "programming_language",
    "c++": "programming_language",
    "c#": "programming_language",
    "go": "programming_language",
    "rust": "programming_language",
    "ruby": "programming_language",
    "php": "programming_language",
    "swift": "programming_language",
    "kotlin": "programming_language",
    "scala": "programming_language",
    
    # Frameworks
    "react": "framework",
    "react.js": "framework",
    "vue": "framework",
    "vue.js": "framework",
    "angular": "framework",
    "django": "framework",
    "flask": "framework",
    "spring": "framework",
    "express": "framework",
    "fastapi": "framework",
    
    # Databases
    "postgresql": "database",
    "mysql": "database",
    "mongodb": "database",
    "redis": "database",
    "sqlite": "database",
    "elasticsearch": "database",
    
    # Cloud/DevOps
    "aws": "cloud",
    "azure": "cloud",
    "gcp": "cloud",
    "docker": "devops",
    "kubernetes": "devops",
    "git": "devops",
    "ci/cd": "devops",
    
    # Other
    "sql": "other",
    "nosql": "other",
    "graphql": "other",
    "rest": "other",
    "api": "other",
}


def normalize_skill_name(raw_skill_name: str) -> str:
    """Normalize a skill name to canonical form."""
    # Step 1: Trim whitespace
    normalized = raw_skill_name.strip()
    
    # Step 2: Lowercase for alias lookup
    normalized_lower = normalized.lower()
    
    # Step 3: Apply aliases first (before any other normalization)
    if normalized_lower in SKILL_ALIASES:
        return SKILL_ALIASES[normalized_lower]
    
    # Step 4: Check if this is a preserve-format skill
    if normalized_lower in PRESERVE_FORMAT_SKILLS:
        return normalized_lower
    
    # Step 5: For other skills, lowercase and remove special characters
    # Keep only alphanumeric and spaces
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized_lower)
    
    # Step 6: Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def categorize_skill(skill_name: str) -> str:
    """Assign a category to a skill based on canonical name."""
    normalized = skill_name.lower()
    return SKILL_CATEGORIES.get(normalized, "other")


def normalize_skill(raw_skill_name: str, db: Session) -> Skill:
    """Normalize a skill name and ensure it exists in the database."""
    # Normalize the skill name
    canonical_name = normalize_skill_name(raw_skill_name)
    
    # Check if skill already exists
    existing = db.query(Skill).filter(Skill.canonical_name == canonical_name).first()
    if existing:
        return existing
    
    # Determine category
    category = categorize_skill(canonical_name)
    
    # Create new skill
    new_skill = Skill(canonical_name=canonical_name, category=category)
    db.add(new_skill)
    db.flush()
    return new_skill