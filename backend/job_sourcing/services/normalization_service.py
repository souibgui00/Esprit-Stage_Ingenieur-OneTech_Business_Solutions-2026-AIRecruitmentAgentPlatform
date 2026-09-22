import re
import hashlib
import json
from datetime import datetime
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from job_sourcing.connectors.base import JobOfferDTO
from job_sourcing.models import JobOffer, JobSource, ContractType, OfferStatus, JobSkill, CertificationStandard
from cv_management.skill_normalization import normalize_skill, normalize_skill_name

class JobNormalizationService:
    @staticmethod
    def clean_html(text: str) -> str:
        """Strip HTML tags and clean up whitespace."""
        if not text:
            return ""
        # Remove HTML formatting
        soup = BeautifulSoup(text, "html.parser")
        cleaned = soup.get_text(separator=" ")
        # Clean extra spaces and newlines
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    @staticmethod
    def detect_contract_type(description: str, title: str) -> Optional[ContractType]:
        """Detect contract type from title or description text using heuristics."""
        combined_text = f"{title} {description}".upper()

        if re.search(r'\b(CDI|DURÉE INDÉTERMINÉE|PERMANENT)\b', combined_text):
            return ContractType.CDI
        if re.search(r'\b(CDD|DURÉE DÉTERMINÉE|TEMPORAIRE|CONTRACT)\b', combined_text):
            return ContractType.CDD
        if re.search(r'\b(STAGE|STAGIAIRE|INTERN|INTERNSHIP)\b', combined_text):
            return ContractType.STAGE
        if re.search(r'\b(FREELANCE|INDÉPENDANT|CONTRACTOR|CONSULTANT EXTERNE)\b', combined_text):
            return ContractType.FREELANCE

        return None

    @staticmethod
    def extract_required_skills(description: str) -> tuple[List[str], List[str]]:
        """Extract required skills from job description, distinguishing essential vs nice-to-have.

        All extracted skill strings are passed through normalize_skill_name() so the canonical
        names stored in JobSkill match those stored in CVSkill (same Skill table rows).

        Returns:
            tuple: (essential_skills, nice_to_have_skills) — lists of canonical names
        """
        if not description:
            return [], []

        from cv_management.skill_normalization import normalize_skill_name

        # Expanded skill patterns — order matters, more specific first
        skill_patterns = [
            # Languages
            r'\b(Python|Java(?:Script|FX)?|TypeScript|Go|Rust|C\+\+|C#|PHP|Ruby|Swift|Kotlin|Scala|R)\b',
            # Frameworks & libraries (specific before generic)
            r'\b(Spring\s+Boot|Spring|React\s+Native|React|Next\.js|NestJS|Angular|Vue(?:\.js)?|Node\.js|'
            r'Django|Flask|FastAPI|Express(?:\.js)?|Symfony|Laravel|Rails)\b',
            # ML / AI
            r'\b(Machine\s+Learning|Deep\s+Learning|NLP|Natural\s+Language\s+Processing|'
            r'Computer\s+Vision|Data\s+Science|Scikit[- ]?Learn|Scikit-learn|'
            r'Sentence[- ]?BERT|Random\s+Forest|TensorFlow|PyTorch|Keras|'
            r'LLM|Large\s+Language\s+Models|RAG|Retrieval\s+Augmented\s+Generation|'
            r'Vector\s+Embeddings|Embeddings|AI|Artificial\s+Intelligence)\b',
            # Cloud & DevOps
            r'\b(Docker|Kubernetes|K8s|AWS|Amazon\s+Web\s+Services|Azure|GCP|Google\s+Cloud|'
            r'Terraform|Ansible|Jenkins|GitHub\s+Actions|GitLab\s+CI|CI/CD|CI\s*CD|'
            r'Prometheus|Grafana|SonarQube|Nexus|Helm)\b',
            # Databases
            r'\b(SQL|PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch|SQLite|Cassandra|PgVector)\b',
            # Dev practices & tools
            r'\b(Git|GitHub|GitLab|Agile|Scrum|Jira|Confluence|DevOps|'
            r'Domain[- ]Driven\s+Design|DDD|TDD|BDD|Microservices|REST|GraphQL|API|gRPC)\b',
            # Web
            r'\b(HTML5?|CSS3?|SASS|SCSS|Webpack|Vite)\b',
            # Systems
            r'\b(Linux|Unix|Bash|Shell)\b',
        ]

        essential_skills = set()
        nice_to_have_skills = set()

        # Extract skills from full description
        for pattern in skill_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                canonical = normalize_skill_name(match.strip())
                if canonical and len(canonical) <= 50:
                    essential_skills.add(canonical)

        # Refine: look for explicit "Required" sections → keep as essential
        req_section = re.search(
            r'(?:required\s+skills?|requirements?|qualifications?|'
            r'compétences\s+requises?|must\s+have|you\s+(?:must|need|have))[:\s]*([^.]{10,300})',
            description,
            re.IGNORECASE
        )
        if req_section:
            section_text = req_section.group(1)
            for pattern in skill_patterns:
                for match in re.findall(pattern, section_text, re.IGNORECASE):
                    canonical = normalize_skill_name(match.strip())
                    if canonical and len(canonical) <= 50:
                        essential_skills.add(canonical)

        # Look for "Nice to have" / "Preferred" sections → nice_to_have
        nice_section = re.search(
            r'(?:nice\s+to\s+have|preferred|plus|bonus|desirable|'
            r'souhaitable|un\s+plus|appréci[eé])[:\s]*([^.]{10,300})',
            description,
            re.IGNORECASE
        )
        if nice_section:
            section_text = nice_section.group(1)
            for pattern in skill_patterns:
                for match in re.findall(pattern, section_text, re.IGNORECASE):
                    canonical = normalize_skill_name(match.strip())
                    if canonical and len(canonical) <= 50:
                        nice_to_have_skills.add(canonical)

        # Don't double-count
        essential_skills -= nice_to_have_skills

        filtered_essential = sorted(essential_skills)[:15]
        filtered_nice = sorted(nice_to_have_skills)[:10]

        return filtered_essential, filtered_nice

    @staticmethod
    def extract_certifications(description: str, db: Session) -> Tuple[List[str], List[str]]:
        """
        Extract required and preferred certifications from job description.
        
        Conservative approach:
        - Only extract certifications from explicit required/preferred sections
        - Use whitelist from CertificationStandard table
        - Ignore certifications without explicit required/preferred context
        - Do not treat technologies as certifications
        
        Returns:
            tuple: (required_certifications, preferred_certifications) — lists of canonical names
        """
        if not description:
            return [], []
        
        # Load certification standards into memory for efficiency
        cert_standards = db.query(CertificationStandard).all()
        cert_map = {cs.canonical_name.lower(): cs.canonical_name for cs in cert_standards}
        alias_map = {}
        for cs in cert_standards:
            for alias in cs.aliases:
                alias_map[alias.lower()] = cs.canonical_name
        
        required = []
        preferred = []
        
        # Extract certifications from required sections (find all occurrences)
        required_section_matches = re.finditer(
            r'(?:required certification|certification required|must have certification|mandatory certification)\s*(?:[:\.\,]|is|are)?\s*([^.]{0,500})',
            description,
            re.IGNORECASE
        )
        for match in required_section_matches:
            section_text = match.group(1)
            JobNormalizationService._extract_certifications_from_text(
                section_text, cert_map, alias_map, required
            )
        
        # Extract certifications from preferred sections (find all occurrences)
        preferred_section_matches = re.finditer(
            r'(?:preferred certification|certification preferred|nice to have certification|bonus certification|desirable certification)\s*(?:[:\.\,]|is|are)?\s*([^.]{0,500})',
            description,
            re.IGNORECASE
        )
        for match in preferred_section_matches:
            section_text = match.group(1)
            JobNormalizationService._extract_certifications_from_text(
                section_text, cert_map, alias_map, preferred
            )
        
        # Remove duplicates
        required = list(set(required))
        preferred = list(set(preferred))
        
        # Remove from preferred if already in required
        preferred = [c for c in preferred if c not in required]
        
        return required, preferred
    
    @staticmethod
    def _extract_certifications_from_text(
        text: str, 
        cert_map: dict, 
        alias_map: dict, 
        results: list
    ):
        """Extract certifications from text using whitelist and normalization."""
        text_lower = text.lower()
        
        # Check all certification standards and aliases
        for canonical_lower, canonical_name in cert_map.items():
            # Check exact canonical name
            if canonical_lower in text_lower:
                if canonical_name not in results:
                    results.append(canonical_name)
        
        # Check aliases
        for alias_lower, alias_canonical in alias_map.items():
            if alias_lower in text_lower:
                if alias_canonical not in results:
                    results.append(alias_canonical)




    @classmethod
    def compute_fingerprint(cls, raw_url: str, title: str, company: str) -> str:
        """Compute a unique SHA-256 hash for deduplication."""
        unique_string = f"{raw_url.strip().lower()}:{title.strip().lower()}:{company.strip().lower()}"
        return hashlib.sha256(unique_string.encode('utf-8')).hexdigest()

    @classmethod
    def normalize(cls, dto: JobOfferDTO, source: JobSource, db: Session) -> JobOffer:
        """Convert a raw JobOfferDTO into a clean domain JobOffer entity."""
        title = cls.clean_html(dto.raw_title)
        company = cls.clean_html(dto.raw_company)
        description = cls.clean_html(dto.raw_description)
        location = cls.clean_html(dto.raw_location) if dto.raw_location else None

        fingerprint = cls.compute_fingerprint(dto.raw_url, title, company)
        contract_type = cls.detect_contract_type(description, title)
        raw_essential_skills, raw_nice_to_have_skills = cls.extract_required_skills(description)

        # Normalize skills and create JobSkill records with importance
        job_skills = []
        for raw_skill in raw_essential_skills:
            skill = normalize_skill(raw_skill, db)
            job_skills.append((skill, "essential"))
        
        for raw_skill in raw_nice_to_have_skills:
            skill = normalize_skill(raw_skill, db)
            job_skills.append((skill, "nice_to_have"))

        # Simple date parsing logic
        posted_at = None
        if dto.raw_posted_date:
            try:
                # Expect ISO or common format, fallback to now if unparseable
                posted_at = datetime.fromisoformat(dto.raw_posted_date)
            except ValueError:
                posted_at = datetime.utcnow()
        else:
            posted_at = datetime.utcnow()

        # Extract certifications
        required_certs, preferred_certs = cls.extract_certifications(description, db)

        job_offer = JobOffer(
            source_id=source.id,
            source_url=dto.raw_url,
            fingerprint=fingerprint,
            title=title,
            company=company,
            location=location,
            description=description,
            contract_type=contract_type,
            required_skills=json.dumps([s[0].canonical_name for s in job_skills if hasattr(s[0], 'canonical_name')]) if job_skills else None,  # Keep for backward compatibility
            posted_at=posted_at,
            collected_at=datetime.utcnow(),
            status=OfferStatus.NEW,
            required_certifications=required_certs,
            preferred_certifications=preferred_certs
        )
        
        # Add job offer to session to get ID
        db.add(job_offer)
        db.flush()
        
        # Create JobSkill records (junction table) with importance
        for skill, importance in job_skills:
            job_skill = JobSkill(
                job_offer_id=job_offer.id,
                skill_id=skill.id,
                importance=importance
            )
            db.add(job_skill)
        
        return job_offer
