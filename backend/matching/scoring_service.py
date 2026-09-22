"""
Scoring Service - Implements the 6-factor scoring architecture for CV-Job matching.

Factors:
- Skills: 35 points
- Experience relevance: 20 points
- Seniority: 10 points
- Semantic similarity: 15 points
- LLM qualitative evaluation: 10 points
- Certification bonus: 0-5 points (capped)
"""
import uuid
import re
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session
from cv_management.models import CV, CVSkill, Experience, Certification, Skill
from job_sourcing.models import JobOffer, JobSkill


class ScoringService:
    """Service for calculating individual scoring factors in the 6-factor architecture."""
    
    # Proficiency level mappings
    PROFICIENCY_SCORES = {
        "BEGINNER": 0.5,
        "INTERMEDIATE": 0.75,
        "ADVANCED": 0.9,
        "EXPERT": 1.0,
        "UNKNOWN": 0.6  # Default when proficiency is unknown
    }
    
    # Seniority level mappings
    SENIORITY_LEVELS = {
        "INTERN": 1,
        "JUNIOR": 2,
        "MID": 3,
        "SENIOR": 4,
        "LEAD": 5,
        "MANAGER": 6,
        "DIRECTOR": 7,
        "CTO": 8
    }
    
    # Seniority detection patterns (pattern, numeric_level)
    SENIORITY_PATTERNS = [
        (r'\b(intern|stagiaire|internship)\b', 1),
        (r'\b(junior|associate|entry)\b', 2),
        (r'\b(mid|middle|regular)\b', 3),
        (r'\b(senior|sr\.|experienced)\b', 4),
        (r'\b(lead|principal|staff)\b', 5),
        (r'\b(manager|head|chief)\b', 6),
        (r'\b(director|vp)\b', 7),
        (r'\b(cto|chief\s+technology\s+officer)\b', 8)
    ]
    
    @staticmethod
    def calculate_skills_score(cv_id: uuid.UUID, job_offer_id: uuid.UUID, db: Session) -> Dict:
        """
        Calculate skills score (35 points max).
        
        Algorithm:
        - Essential skills: 70% of score (24.5 points)
        - Nice-to-have skills: 20% of score (7 points)
        - Proficiency alignment: 10% of score (3.5 points)
        
        Returns dict with score and breakdown.
        """
        # Get CV skills with proficiency
        cv_skills_query = (
            db.query(Skill.canonical_name, CVSkill.proficiency)
            .join(CVSkill, CVSkill.skill_id == Skill.id)
            .filter(CVSkill.cv_id == cv_id)
            .all()
        )
        cv_skill_dict = {skill: prof for skill, prof in cv_skills_query}
        cv_skill_names = set(cv_skill_dict.keys())
        
        # Get job skills with importance
        job_skills_query = (
            db.query(Skill.canonical_name, JobSkill.importance)
            .join(JobSkill, JobSkill.skill_id == Skill.id)
            .filter(JobSkill.job_offer_id == job_offer_id)
            .all()
        )
        
        essential_job_skills = set()
        nice_to_have_job_skills = set()
        
        for skill_name, importance in job_skills_query:
            if importance == "essential":
                essential_job_skills.add(skill_name)
            elif importance == "nice_to_have":
                nice_to_have_job_skills.add(skill_name)
        
        # Helper function for matching CV skill vs Job skill
        def skills_match(cv_skill: str, job_skill: str) -> bool:
            c, j = cv_skill.lower(), job_skill.lower()
            if c == j:
                return True
            # Compound skill matching (e.g. 'reactnextjs' containing 'react' or 'nextjs')
            if j in c or c in j:
                return True
            return False

        # Calculate matches with compound / alias support
        matched_essential = set()
        for j_skill in essential_job_skills:
            if any(skills_match(c_skill, j_skill) for c_skill in cv_skill_names):
                matched_essential.add(j_skill)

        matched_nice_to_have = set()
        for j_skill in nice_to_have_job_skills:
            if any(skills_match(c_skill, j_skill) for c_skill in cv_skill_names):
                matched_nice_to_have.add(j_skill)

        missing_essential = essential_job_skills - matched_essential
        missing_nice_to_have = nice_to_have_job_skills - matched_nice_to_have
        
        # Essential skills score (70% of 35 = 24.5 points)
        essential_score = 0.0
        if essential_job_skills:
            essential_ratio = len(matched_essential) / len(essential_job_skills)
            essential_score = essential_ratio * 24.5
        
        # Nice-to-have skills score (20% of 35 = 7 points)
        nice_score = 0.0
        if nice_to_have_job_skills:
            nice_ratio = len(matched_nice_to_have) / len(nice_to_have_job_skills)
            nice_score = nice_ratio * 7.0
        
        # Proficiency bonus (10% of 35 = 3.5 points)
        proficiency_score = 0.0
        if matched_essential:
            avg_proficiency = 0.0
            for skill in matched_essential:
                prof = cv_skill_dict.get(skill, "UNKNOWN")
                avg_proficiency += ScoringService.PROFICIENCY_SCORES.get(prof, 0.6)
            avg_proficiency /= len(matched_essential)
            proficiency_score = avg_proficiency * 3.5
        
        total_score = essential_score + nice_score + proficiency_score
        total_score = min(35.0, total_score)  # Cap at 35
        
        return {
            "skills_score": round(total_score, 2),
            "skills_max": 35.0,
            "matched_essential_skills": sorted(list(matched_essential)),
            "matched_nice_to_have_skills": sorted(list(matched_nice_to_have)),
            "missing_essential_skills": sorted(list(missing_essential)),
            "missing_nice_to_have_skills": sorted(list(missing_nice_to_have)),
            "essential_score": round(essential_score, 2),
            "nice_to_have_score": round(nice_score, 2),
            "proficiency_score": round(proficiency_score, 2)
        }
    
    @staticmethod
    def calculate_experience_score(cv_id: uuid.UUID, job_offer_id: uuid.UUID, db: Session) -> Dict:
        """
        Calculate experience relevance score (20 points max).
        
        Algorithm:
        - Total years of experience: 40% (8 points)
        - Relevant experience: 40% (8 points)
        - Career progression: 20% (4 points)
        
        Returns dict with score and breakdown.
        """
        # Get CV experiences
        cv_experiences = db.query(Experience).filter_by(cv_id=cv_id).all()
        
        # Get job offer for requirements extraction
        job_offer = db.get(JobOffer, job_offer_id)
        if not job_offer:
            return {"experience_score": 0.0, "experience_max": 20.0, "relevant_experience": []}
        
        # Calculate total years of experience
        total_years = 0.0
        for exp in cv_experiences:
            start = exp.start_date
            end = exp.end_date if exp.end_date else None
            
            if start:
                from datetime import date
                end_date = end if end else date.today()
                years = (end_date - start).days / 365.25
                total_years += years
        
        # Extract required years from job description
        required_years = ScoringService._extract_required_years(job_offer.description)
        
        # Years match score (40% of 20 = 8 points)
        years_score = 0.0
        if required_years:
            if total_years >= required_years:
                years_score = 8.0
            elif total_years >= required_years * 0.8:
                years_score = 6.0
            elif total_years >= required_years * 0.5:
                years_score = 4.0
            else:
                years_score = 2.0
        else:
            # No requirement specified, give partial credit for having experience
            years_score = min(8.0, total_years * 0.5)
        
        # Relevant experience score (40% of 20 = 8 points)
        relevant_exp = ScoringService._calculate_relevant_experience(cv_experiences, job_offer)
        relevant_score = min(8.0, relevant_exp * 2.0)
        
        # Career progression score (20% of 20 = 4 points)
        progression_score = ScoringService._calculate_career_progression(cv_experiences)
        
        total_score = years_score + relevant_score + progression_score
        total_score = min(20.0, total_score)
        
        return {
            "experience_score": round(total_score, 2),
            "experience_max": 20.0,
            "total_years": round(total_years, 1),
            "required_years": required_years,
            "years_score": round(years_score, 2),
            "relevant_score": round(relevant_score, 2),
            "progression_score": round(progression_score, 2),
            "relevant_experience": relevant_exp
        }
    
    @staticmethod
    def _extract_required_years(description: str) -> Optional[int]:
        """Extract required years of experience from job description."""
        if not description:
            return None
        
        # Look for patterns like "3+ years", "3-5 years", "3 years experience"
        patterns = [
            r'(\d+)\+?\s*years?\s*(?:of\s*)?(?:experience)?',
            r'(\d+)\s*-\s*(\d+)\s*years?',
            r'(\d+)\s*ans?\s*(?:d\'expérience)?'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                try:
                    if match.lastindex == 2:  # Range like "3-5"
                        return int(match.group(1))  # Use lower bound
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    @staticmethod
    def _calculate_relevant_experience(experiences: List[Experience], job_offer: JobOffer) -> float:
        """Calculate relevance score based on experience titles and job requirements."""
        if not experiences:
            return 0.0
        
        # Extract keywords from job title and description
        job_keywords = set()
        job_text = f"{job_offer.title} {job_offer.description}".lower()
        
        # Common tech keywords
        tech_keywords = [
            'python', 'java', 'javascript', 'react', 'angular', 'node', 'django',
            'docker', 'kubernetes', 'aws', 'azure', 'sql', 'machine learning',
            'data', 'devops', 'frontend', 'backend', 'fullstack', 'mobile'
        ]
        
        for keyword in tech_keywords:
            if keyword in job_text:
                job_keywords.add(keyword)
        
        # Score each experience based on keyword overlap
        relevance_total = 0.0
        for exp in experiences:
            exp_text = f"{exp.title} {exp.description or ''}".lower()
            overlap = len(job_keywords & set(exp_text.split()))
            relevance_total += min(2.0, overlap)  # Max 2 points per experience
        
        return min(4.0, relevance_total)  # Cap at 4.0 for normalization
    
    @staticmethod
    def _calculate_career_progression(experiences: List[Experience]) -> float:
        """Calculate career progression score based on title seniority."""
        if len(experiences) < 2:
            return 1.0  # Neutral score for single/no experience
        
        # Sort by start date
        sorted_exps = sorted(experiences, key=lambda x: x.start_date)
        
        progression_count = 0
        prev_level = 0
        
        for exp in sorted_exps:
            current_level = ScoringService._detect_seniority_level(exp.title)
            if current_level > prev_level:
                progression_count += 1
            prev_level = current_level
        
        # Score based on progression (max 4 points)
        progression_score = min(4.0, progression_count * 1.5)
        return progression_score
    
    @staticmethod
    def calculate_seniority_score(cv_id: uuid.UUID, job_offer_id: uuid.UUID, db: Session) -> Dict:
        """
        Calculate seniority matching score (10 points max).
        
        Algorithm:
        - Detect CV seniority from experience titles
        - Detect job seniority from title/description
        - Score alignment (exact match = 10, off by 1 = 7, off by 2 = 4, off by 3+ = 0)
        
        Returns dict with score and breakdown.
        """
        # Get CV experiences
        cv_experiences = db.query(Experience).filter_by(cv_id=cv_id).all()
        
        # Get job offer
        job_offer = db.get(JobOffer, job_offer_id)
        if not job_offer:
            return {"seniority_score": 0.0, "seniority_max": 10.0, "candidate_seniority": "UNKNOWN", "job_seniority": "UNKNOWN"}
        
        # Detect candidate seniority (use most recent/most senior)
        candidate_seniority = "UNKNOWN"
        max_level = 0
        for exp in cv_experiences:
            level = ScoringService._detect_seniority_level(exp.title)
            if level > max_level:
                max_level = level
                candidate_seniority = ScoringService._level_to_string(level)
        
        # Detect job seniority
        job_seniority = ScoringService._detect_seniority_level(job_offer.title)
        job_seniority_str = ScoringService._level_to_string(job_seniority)
        
        # Calculate alignment score
        level_diff = abs(max_level - job_seniority)
        
        if level_diff == 0:
            score = 10.0
        elif level_diff == 1:
            score = 7.0
        elif level_diff == 2:
            score = 4.0
        else:
            score = 0.0
        
        return {
            "seniority_score": round(score, 2),
            "seniority_max": 10.0,
            "candidate_seniority": candidate_seniority,
            "job_seniority": job_seniority_str,
            "level_difference": level_diff
        }
    
    @staticmethod
    def _detect_seniority_level(text: str) -> int:
        """Detect seniority level from text (title or description)."""
        if not text:
            return 0
        
        text_lower = text.lower()
        
        # Intern / Stagiaire / Trainee roles take absolute priority
        if re.search(r'\b(intern|stagiaire|internship|trainee|alternant|alternance)\b', text_lower):
            return 1  # INTERN
            
        max_level = 0
        for pattern, level in ScoringService.SENIORITY_PATTERNS:
            if re.search(pattern, text_lower):
                max_level = max(max_level, level)
        
        return max_level
    
    @staticmethod
    def _level_to_string(level: int) -> str:
        """Convert numeric level to string representation."""
        for string_level, numeric_level in ScoringService.SENIORITY_LEVELS.items():
            if numeric_level == level:
                return string_level
        return "UNKNOWN"
    
    @staticmethod
    def calculate_certification_bonus(cv_id: uuid.UUID, job_offer_id: uuid.UUID, db: Session) -> Dict:
        """
        Calculate certification bonus (0-5 points max, strictly capped).
        
        Algorithm:
        - Extract CV certifications
        - Get structured certification data from job offer (required_certifications, preferred_certifications)
        - Match certifications using exact/canonical/alias matching (no fuzzy, no LLM)
        - 2 points per required cert, 1 point per preferred cert
        - Strict cap at 5 points
        
        Returns dict with bonus and breakdown.
        """
        # Get CV certifications
        cv_certs = db.query(Certification).filter_by(cv_id=cv_id).all()
        cv_cert_names = set(cert.name.lower() for cert in cv_certs)
        
        # Get job offer
        job_offer = db.get(JobOffer, job_offer_id)
        if not job_offer:
            return {"certification_bonus": 0.0, "certification_max": 5.0, "matched_certifications": []}
        
        # Get structured certification data from job offer
        # Use the new structured fields instead of text extraction
        required_certs = job_offer.required_certifications if job_offer.required_certifications else []
        preferred_certs = job_offer.preferred_certifications if job_offer.preferred_certifications else []
        
        # Normalize job certifications to lowercase for matching
        required_certs_lower = set(cert.lower() for cert in required_certs)
        preferred_certs_lower = set(cert.lower() for cert in preferred_certs)
        
        # Calculate matches using exact/canonical/alias matching
        matched_required = cv_cert_names & required_certs_lower
        matched_preferred = cv_cert_names & preferred_certs_lower
        
        # Calculate bonus (2 points per required, 1 point per preferred)
        bonus = len(matched_required) * 2.0 + len(matched_preferred) * 1.0
        
        # Strict cap at 5 points
        bonus = min(5.0, bonus)
        
        return {
            "certification_bonus": round(bonus, 2),
            "certification_max": 5.0,
            "matched_certifications": sorted(list(matched_required | matched_preferred)),
            "required_certifications": required_certs,
            "preferred_certifications": preferred_certs
        }