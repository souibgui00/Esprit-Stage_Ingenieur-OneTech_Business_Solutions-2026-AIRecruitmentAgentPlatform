import uuid
import os
import time
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel as PydanticBaseModel

class UpdatePersonalInfoRequest(PydanticBaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    salary_expectation: str | None = None

from shared.database import get_db
from cv_management.models import CV, CVStatus, PersonalInfo, Experience, Education, CVSkill, Skill, Certification
from cv_management.schemas import CVResponse
from cv_management.parsing_service import parse_cv
from matching.matching_service import MatchingService
from user_management.dependencies import get_current_user
from user_management.models import User

from cv_management.adapters.pdf_text_extractor import PdfTextExtractor
from cv_management.adapters.groq_llm_extractor import GroqLLMExtractor
from cv_management.adapters.e5_embedding_provider import E5EmbeddingProvider

router = APIRouter(prefix="/cv", tags=["cv"])

UPLOAD_DIR = Path("uploaded_cvs")
UPLOAD_DIR.mkdir(exist_ok=True)

# Instantiate adapters as singletons at startup
text_extractor = PdfTextExtractor()
llm_extractor = GroqLLMExtractor()
embedding_provider = E5EmbeddingProvider()

# Simple in-memory rate limiting for CV uploads
upload_attempts = {}

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 10MB
UPLOAD_RATE_LIMIT = 5  # uploads per minute per user


def _enrich_cv(cv: CV, db: Session) -> CV:
    """Load all related data for a CV so the response schema can serialize it."""
    cv.personal_info = db.query(PersonalInfo).filter_by(cv_id=cv.id).first()
    cv.experiences = db.query(Experience).filter_by(cv_id=cv.id).all()
    cv.educations = db.query(Education).filter_by(cv_id=cv.id).all()
    cv.certifications = db.query(Certification).filter_by(cv_id=cv.id).all()

    # Load skills via join
    cv_skills = db.query(CVSkill).filter_by(cv_id=cv.id).all()
    skill_ids = [cs.skill_id for cs in cv_skills]
    cv.skills = db.query(Skill).filter(Skill.id.in_(skill_ids)).all() if skill_ids else []

    return cv


def check_upload_rate_limit(user_id: uuid.UUID):
    """Check if user has exceeded upload rate limit (5 uploads per minute)."""
    current_time = time.time()
    user_attempts = upload_attempts.get(str(user_id), [])
    
    # Remove attempts older than 1 minute
    user_attempts = [t for t in user_attempts if current_time - t < 60]
    
    if len(user_attempts) >= UPLOAD_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Trop de téléchargements. Maximum {UPLOAD_RATE_LIMIT} uploads par minute."
        )
    
    # Add current attempt
    user_attempts.append(current_time)
    upload_attempts[str(user_id)] = user_attempts


@router.get("", response_model=List[CVResponse])
@router.get("/", response_model=List[CVResponse])
def list_cvs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Liste tous les CVs de l'utilisateur connecté avec leurs données parsées."""
    cvs = db.query(CV).filter(CV.user_id == current_user.id).order_by(CV.created_at.desc()).all()
    return [_enrich_cv(cv, db) for cv in cvs]


@router.get("/{cv_id}", response_model=CVResponse)
def get_cv(
    cv_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupère un CV par son ID avec toutes les données parsées."""
    cv = db.get(CV, cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail="CV non trouvé")
    if cv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return _enrich_cv(cv, db)


@router.post("/upload", response_model=CVResponse)
def upload_cv(
    file: UploadFile,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload et parse un fichier PDF CV pour l'utilisateur connecté."""
    # Check rate limit
    check_upload_rate_limit(current_user.id)
    
    # Check file extension
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont supportés pour l'instant.")
    
    # Check file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux. Maximum {MAX_FILE_SIZE_MB} MB autorisé."
        )
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    
    # Read file content for MIME validation
    file_content = file.file.read()
    file.file.seek(0)  # Reset to beginning
    
    # Validate MIME type using filetype
    import filetype
    kind = filetype.guess(file_content)
    
    if kind is None or kind.mime != "application/pdf":
        raise HTTPException(status_code=400, detail="Le fichier n'est pas un PDF valide.")
    
    # Generate CV UUID first for filename
    cv_uuid = uuid.uuid4()
    file_path = UPLOAD_DIR / f"{cv_uuid}.pdf"
    
    # Save file to storage
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur lors de l'enregistrement du fichier.")

    # Enforce SINGLE ACTIVE CV rule: replace/delete any existing CVs for this user
    existing_cvs = db.query(CV).filter_by(user_id=current_user.id).all()
    for old_cv in existing_cvs:
        try:
            MatchingService.invalidate_cv_matches(old_cv.id, db)
            old_path = Path(old_cv.raw_file_url)
            if old_path.exists():
                old_path.unlink()
        except Exception:
            pass
        db.delete(old_cv)
    db.commit()

    cv = CV(
        id=cv_uuid,
        user_id=current_user.id,
        filename=file.filename,
        raw_file_url=str(file_path),
        language="FR",
        status=CVStatus.UPLOADED,
    )
    
    try:
        db.add(cv)
        db.commit()
        db.refresh(cv)

        # Parse automatiquement le CV après upload
        parse_cv(cv, db, text_extractor, llm_extractor, embedding_provider)
        
        # Invalidate existing matches for this CV (force recalculation with new data)
        MatchingService.invalidate_cv_matches(cv.id, db)
        
        db.refresh(cv)
    except Exception as e:
        # If database operation fails, cleanup the uploaded file
        if file_path.exists():
            os.unlink(file_path)
        db.rollback()
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du CV.")

    return _enrich_cv(cv, db)


@router.put("/{cv_id}/personal-info")
def update_personal_info(
    cv_id: uuid.UUID,
    payload: UpdatePersonalInfoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cv = db.get(CV, cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail="CV non trouvé")
    if cv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    personal_info = db.query(PersonalInfo).filter_by(cv_id=cv_id).first()
    if not personal_info:
        raise HTTPException(status_code=404, detail="Informations personnelles non trouvées")
    
    if payload.full_name is not None:
        personal_info.full_name = payload.full_name
    if payload.email is not None:
        personal_info.email = payload.email
    if payload.phone is not None:
        personal_info.phone = payload.phone
    if payload.location is not None:
        personal_info.location = payload.location
    if payload.linkedin_url is not None:
        personal_info.linkedin_url = payload.linkedin_url
    if payload.github_url is not None:
        personal_info.github_url = payload.github_url
    if payload.salary_expectation is not None:
        personal_info.salary_expectation = payload.salary_expectation
    
    db.commit()
    db.refresh(personal_info)
    return {
        "status": "updated",
        "full_name": personal_info.full_name,
        "email": personal_info.email,
        "phone": personal_info.phone,
        "location": personal_info.location,
        "linkedin_url": personal_info.linkedin_url,
        "github_url": personal_info.github_url,
        "salary_expectation": personal_info.salary_expectation
    }


@router.delete("/{cv_id}")
def delete_cv(
    cv_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprime un CV de l'utilisateur connecté ainsi que toutes ses données associées."""
    cv = db.get(CV, cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail="CV non trouvé")
    if cv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    # Delete file from storage
    file_path = Path(cv.raw_file_url)
    if file_path.exists():
        try:
            os.unlink(file_path)
        except Exception as e:
            # Log the error but don't fail the deletion
            print(f"Warning: Could not delete file {file_path}: {e}")
    
    # Delete CV - database CASCADE will handle related records
    db.delete(cv)
    db.commit()
    return {"status": "deleted", "cv_id": str(cv_id)}


@router.get("/{cv_id}/status")
def get_cv_status(
    cv_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupère le statut de traitement d'un CV."""
    cv = db.get(CV, cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail="CV non trouvé")
    if cv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    return {
        "cv_id": str(cv.id),
        "status": cv.status.value,
        "created_at": cv.created_at.isoformat() if cv.created_at else None,
        "parsed_at": cv.parsed_at.isoformat() if cv.parsed_at else None,
        "failure_reason": cv.failure_reason
    }


@router.post("/{cv_id}/reparse", response_model=CVResponse)
def reparse_cv(
    cv_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Relance le parsing d'un CV (peut être utilisé pour les CVs ayant échoué ou pour mettre à jour l'extraction)."""
    cv = db.get(CV, cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail="CV non trouvé")
    if cv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    # Check if file still exists
    file_path = Path(cv.raw_file_url)
    if not file_path.exists():
        raise HTTPException(status_code=400, detail="Fichier CV introuvable sur le disque")
    
    # Re-parse the CV using the existing parsing pipeline
    parse_cv(cv, db, text_extractor, llm_extractor, embedding_provider)
    
    # Invalidate existing matches for this CV (force recalculation with new data)
    MatchingService.invalidate_cv_matches(cv.id, db)
    
    db.refresh(cv)
    
    return _enrich_cv(cv, db)