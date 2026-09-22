from sqlalchemy.orm import Session
import re
from cv_management.models import CV, Experience, Education, CVSkill, PersonalInfo, CVEmbedding, Certification, CVStatus
from cv_management.date_parsing import parse_flexible_date
from cv_management.skill_normalization import normalize_skill
from cv_management.schemas import ParsedCVData
from matching.matching_service import MatchingService

from cv_management.ports.text_extractor import ITextExtractor
from cv_management.ports.llm_extractor import ILLMExtractor
from cv_management.ports.embedding_provider import IEmbeddingProvider
from cv_management.adapters.pdf_text_extractor import (
    PDFExtractionError,
    PDFMalformedError,
    PDFEncryptedError,
    PDFScannedError
)


def validate_email(email: str) -> bool:
    """Validate email format. Returns True if valid or None, False if invalid format."""
    if email is None or email.strip() == "":
        return True  # Optional field, None is valid
    
    # Basic email validation - not overly strict
    # Allows international characters and common formats
    # Pattern: local@domain.tld
    # Local part: letters, numbers, dots, underscores, hyphens, plus (no consecutive dots)
    # Domain: letters, numbers, dots, hyphens
    # TLD: at least 2 letters
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # Additional check: no consecutive dots in local part
    if '..' in email.split('@')[0]:
        return False
    
    return bool(re.match(pattern, email.strip()))


def validate_phone(phone: str) -> bool:
    """Validate phone format. Returns True if valid or None, False if invalid format."""
    if phone is None or phone.strip() == "":
        return True  # Optional field, None is valid
    
    # Flexible phone validation for international formats
    # Allows: +33 6 12 34 56 78, +1 (555) 123-4567, 06 12 34 56 78, etc.
    # Must contain at least 6 digits
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    if not cleaned:
        return False
    
    # Must have at least 6 digits
    digit_count = len(re.sub(r'\+', '', cleaned))
    if digit_count < 6:
        return False
    
    # Must not exceed 15 digits (ITU standard max)
    if digit_count > 15:
        return False
    
    return True

def parse_cv(
    cv: CV, 
    db: Session,
    text_extractor: ITextExtractor,
    llm_extractor: ILLMExtractor,
    embedding_provider: IEmbeddingProvider
) -> CV:
    cv.status = CVStatus.PARSING
    db.commit()

    try:
        # Extract text with specific error handling
        try:
            raw_text = text_extractor.extract_text(cv.raw_file_url)
        except PDFEncryptedError as e:
            raise ValueError(f"PDF extraction failed: {str(e)}")
        except PDFMalformedError as e:
            raise ValueError(f"PDF extraction failed: {str(e)}")
        except PDFScannedError as e:
            raise ValueError(f"PDF extraction failed: {str(e)}")
        except PDFExtractionError as e:
            raise ValueError(f"PDF extraction failed: {str(e)}")
        
        raw_data_dict = llm_extractor.extract_structured_data(raw_text)
        parsed_data = ParsedCVData(**raw_data_dict)
        
        # Validate email and phone formats (if present)
        if not validate_email(parsed_data.email):
            raise ValueError(f"Invalid email format: {parsed_data.email}")
        if not validate_phone(parsed_data.phone):
            raise ValueError(f"Invalid phone format: {parsed_data.phone}")

        # Clean up any existing nested entities for this CV (enables idempotent re-parsing)
        db.query(CVEmbedding).filter_by(cv_id=cv.id).delete()
        db.query(PersonalInfo).filter_by(cv_id=cv.id).delete()
        db.query(Experience).filter_by(cv_id=cv.id).delete()
        db.query(Education).filter_by(cv_id=cv.id).delete()
        db.query(Certification).filter_by(cv_id=cv.id).delete()
        db.query(CVSkill).filter_by(cv_id=cv.id).delete()
        db.flush()

        personal_info = PersonalInfo(
            cv_id=cv.id,
            full_name=parsed_data.full_name,
            email=parsed_data.email,
            phone=parsed_data.phone,
            location=parsed_data.location,
        )
        db.add(personal_info)

        for exp in parsed_data.experiences:
            # Skip experiences with missing required fields
            if not exp.title or not exp.company:
                continue
            exp_start = parse_flexible_date(exp.start_date) if exp.start_date else None
            experience = cv.add_experience(
                title=exp.title,
                company=exp.company,
                start_date=exp_start or parse_flexible_date("2024-01-01"),
                end_date=parse_flexible_date(exp.end_date) if exp.end_date else None,
                description=exp.description,
                is_current=exp.is_current
            )
            db.add(experience)

        for edu in parsed_data.education:
            # Skip education with missing required fields
            if not edu.degree or not edu.institution:
                continue
            edu_start = parse_flexible_date(edu.start_date) if edu.start_date else None
            education = Education(
                cv_id=cv.id,
                degree=edu.degree,
                institution=edu.institution,
                field=edu.field,
                start_date=edu_start or parse_flexible_date("2024-01-01"),
                end_date=parse_flexible_date(edu.end_date) if edu.end_date else None,
            )
            db.add(education)

        for cert in parsed_data.certifications:
            # Skip certifications with missing required fields
            if not cert.name:
                continue
            certification = Certification(
                cv_id=cv.id,
                name=cert.name,
                issuer=cert.issuer,
                date_obtained=parse_flexible_date(cert.date_obtained) if cert.date_obtained else None,
                expiry_date=parse_flexible_date(cert.expiry_date) if cert.expiry_date else None,
            )
            db.add(certification)

        for skill_name in parsed_data.skills:
            skill = normalize_skill(skill_name, db)
            cv_skill = cv.add_skill(
                skill_id=skill.id,
                proficiency="UNKNOWN",
                source="EXPLICIT"
            )
            db.add(cv_skill)

        embedding_vector = embedding_provider.embed(raw_text)
        cv_embedding = CVEmbedding(
            cv_id=cv.id,
            vector=embedding_vector,
            model_name="intfloat/multilingual-e5-large",
        )
        db.add(cv_embedding)

        cv.mark_as_parsed()
        db.commit()
        db.refresh(cv)
    except Exception as e:
        db.rollback()
        cv.mark_as_failed(reason=str(e))
        db.add(cv)  # Re-attach cv to session after rollback
        db.commit()
        db.refresh(cv)

    return cv