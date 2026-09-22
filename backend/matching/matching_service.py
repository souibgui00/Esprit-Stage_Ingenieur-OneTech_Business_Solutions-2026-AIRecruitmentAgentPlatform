import uuid
import json
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from cv_management.models import CV, PersonalInfo, CVSkill, Experience, Skill
from job_sourcing.models import JobOffer, JobSkill
from matching.models import Match, MatchingConfig
from matching.ports.similarity_calculator import IEmbeddingSimilarityCalculator
from matching.ports.llm_matching_evaluator import ILLMMatchingEvaluator
from matching.scoring_service import ScoringService
from user_management.models import UserPreferences


class MatchingService:

    @staticmethod
    def compute_llm_score(matching_points: List[str], gap_points: List[str]) -> float:
        """
        Compute LLM score based on the number of matching points and gap points.
        Base: 55, +10 per matching point (max +40), -12 per gap point (max -48).
        Result bounded between 0.0 and 100.0.
        """
        base_score = 55.0
        bonus = min(len(matching_points), 4) * 10.0
        penalty = min(len(gap_points), 4) * 12.0
        score = base_score + bonus - penalty
        return max(0.0, min(100.0, score))

    @staticmethod
    def passes_user_preferences(job: JobOffer, prefs: Optional[UserPreferences]) -> bool:
        """
        Check if a job matches user preferences with graceful degradation.
        
        Returns True if job should be shown to user, False if it should be filtered out.
        Missing data on either side results in no filtering (returns True).
        
        Args:
            job: JobOffer to check
            prefs: UserPreferences (can be None)
        
        Returns:
            bool: True if job passes preferences or should not be filtered
        """
        if not prefs:
            # No preferences set - no filtering
            return True
        
        # Location filtering
        if prefs.preferred_locations and job.location:
            job_loc_lower = job.location.lower()
            # Check if ANY preferred location matches (substring match, case-insensitive)
            location_match = any(
                loc.lower() in job_loc_lower 
                for loc in prefs.preferred_locations
            )
            if not location_match:
                return False
        
        # Contract type filtering
        if prefs.preferred_contract_types and job.contract_type:
            # Map synonym contract names (e.g., Internship -> STAGE, Permanent -> CDI)
            contract_map = {
                'INTERNSHIP': 'STAGE', 'STAGE': 'STAGE', 'INTERN': 'STAGE',
                'PERMANENT': 'CDI', 'CDI': 'CDI', 'FULL-TIME': 'CDI', 'FULL TIME': 'CDI',
                'FIXED-TERM': 'CDD', 'CDD': 'CDD', 'TEMPORARY': 'CDD',
                'FREELANCE': 'FREELANCE', 'CONTRACTOR': 'FREELANCE',
            }
            user_contracts = set()
            for c in prefs.preferred_contract_types:
                raw_u = c.upper().strip()
                user_contracts.add(contract_map.get(raw_u, raw_u))
            
            job_contract = job.contract_type.value.upper()
            if user_contracts and job_contract not in user_contracts:
                return False
        
        # Remote preference filtering (True = Require Remote Only, False = Open to All)
        if prefs.remote_preference is True and job.location:
            job_loc_lower = job.location.lower()
            if "remote" not in job_loc_lower and "hybrid" not in job_loc_lower:
                return False
        
        return True

    @staticmethod
    def get_or_create_config(user_id: uuid.UUID, db: Session) -> MatchingConfig:
        """
        Get existing MatchingConfig for user or create default config on the fly.
        The 6-factor scoring uses fixed weights, so no configuration is currently needed.
        """
        config = db.query(MatchingConfig).filter_by(user_id=user_id).first()
        if not config:
            config = MatchingConfig(
                user_id=user_id
            )
            db.add(config)
            db.commit()
            db.refresh(config)
        return config

    @staticmethod
    def compute_match(
        cv_id: uuid.UUID,
        job_offer_id: uuid.UUID,
        user_id: uuid.UUID,
        similarity_calculator: IEmbeddingSimilarityCalculator,
        llm_evaluator: ILLMMatchingEvaluator,
        db: Session
    ) -> Match:
        """
        Compute or update the match score and qualitative evaluation between a CV and a JobOffer.
        """
        cv = db.get(CV, cv_id)
        if not cv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trouvé")

        # 1. Security Check: Ownership verification
        if cv.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : ce CV appartient à un autre utilisateur."
            )

        job_offer = db.get(JobOffer, job_offer_id)
        if not job_offer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offre d'emploi non trouvée")

        config = MatchingService.get_or_create_config(user_id, db)

        # 2. Calculate individual scoring factors (6-factor architecture)
        
        # Skills Score (35 points)
        skills_result = ScoringService.calculate_skills_score(cv_id, job_offer_id, db)
        skills_score = skills_result["skills_score"]
        
        # Experience Score (20 points)
        experience_result = ScoringService.calculate_experience_score(cv_id, job_offer_id, db)
        experience_score = experience_result["experience_score"]
        
        # Seniority Score (10 points)
        seniority_result = ScoringService.calculate_seniority_score(cv_id, job_offer_id, db)
        seniority_score = seniority_result["seniority_score"]
        
        # Semantic Similarity (15 points)
        try:
            semantic_sim = similarity_calculator.calculate_single_similarity(cv_id, job_offer_id, db)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
        semantic_score = semantic_sim * 15.0  # Normalize 0-1 to 0-15
        
        # LLM Evaluation (10 points)
        # Build enriched summaries for LLM prompt
        personal_info = db.query(PersonalInfo).filter_by(cv_id=cv_id).first()
        name = personal_info.full_name if personal_info else "Candidat"
        
        experiences = db.query(Experience).filter_by(cv_id=cv_id).all()
        exp_summary = ", ".join([f"{e.title} chez {e.company}" for e in experiences]) if experiences else "Non spécifiée"

        # Explicit skills extraction from CVSkill / Skill
        cv_skills_rows = (
            db.query(Skill.canonical_name)
            .join(CVSkill, CVSkill.skill_id == Skill.id)
            .filter(CVSkill.cv_id == cv_id)
            .all()
        )
        skills_list = [s[0] for s in cv_skills_rows]
        skills_str = ", ".join(skills_list) if skills_list else "Non spécifiées"

        # Explicit skills extraction from JobSkill / Skill (using canonical names)
        job_skills_rows = (
            db.query(Skill.canonical_name)
            .join(JobSkill, JobSkill.skill_id == Skill.id)
            .filter(JobSkill.job_offer_id == job_offer_id)
            .all()
        )
        req_skills_list = [s[0] for s in job_skills_rows]
        req_skills = ", ".join(req_skills_list) if req_skills_list else "Non spécifiées"

        cv_summary = f"Candidat: {name}. Compétences: {skills_str}. Expériences: {exp_summary}."
        job_summary = f"Titre: {job_offer.title}. Entreprise: {job_offer.company}. Lieu: {job_offer.location}. Compétences requises: {req_skills}. Description: {job_offer.description[:600]}"

        # Call LLM evaluator
        assessment = llm_evaluator.evaluate(cv_summary, job_summary)

        matching_points = assessment.get("matching_points", [])
        gap_points = assessment.get("gap_points", [])

        # Use LLM score from assessment, normalize to 0-10
        raw_score_val = assessment.get("score")
        if raw_score_val is None:
            raw_score_val = MatchingService.compute_llm_score(matching_points, gap_points)
        llm_raw_score = float(raw_score_val)
        # Defensive validation: ensure score is in valid range before normalization
        llm_raw_score = max(0.0, min(100.0, llm_raw_score))
        llm_score = (llm_raw_score / 100.0) * 10.0  # Normalize 0-100 to 0-10
        
        # Certification Bonus (0-5 points, capped)
        certification_result = ScoringService.calculate_certification_bonus(cv_id, job_offer_id, db)
        certification_bonus = certification_result["certification_bonus"]
        
        # Calculate base score (sum of 5 weighted factors)
        base_score = skills_score + experience_score + seniority_score + semantic_score + llm_score
        
        # Apply certification bonus with strict cap
        final_score = min(100.0, base_score + certification_bonus)
        final_score = round(max(0.0, final_score), 2)

        # 5. Upsert Match record with new 6-factor scoring
        from sqlalchemy.exc import IntegrityError
        match = db.query(Match).filter_by(cv_id=cv_id, job_offer_id=job_offer_id).first()
        if not match:
            match = Match(
                cv_id=cv_id,
                job_offer_id=job_offer_id,
                semantic_similarity=round(semantic_sim, 4),
                llm_score=llm_score,
                compatibility_score=final_score,
                matching_points=assessment.get("matching_points", []),
                gap_points=assessment.get("gap_points", []),
                summary=assessment.get("summary", ""),
                # New 6-factor fields
                skills_score=skills_score,
                experience_score=experience_score,
                seniority_score=seniority_score,
                semantic_score=semantic_score,
                certification_bonus=certification_bonus
            )
            db.add(match)
        else:
            match.semantic_similarity = round(semantic_sim, 4)
            match.llm_score = llm_score
            match.compatibility_score = final_score
            match.matching_points = assessment.get("matching_points", [])
            match.gap_points = assessment.get("gap_points", [])
            match.summary = assessment.get("summary", "")
            # Update new 6-factor fields
            match.skills_score = skills_score
            match.experience_score = experience_score
            match.seniority_score = seniority_score
            match.semantic_score = semantic_score
            match.certification_bonus = certification_bonus

        try:
            db.commit()
            db.refresh(match)
        except IntegrityError:
            db.rollback()
            match = db.query(Match).filter_by(cv_id=cv_id, job_offer_id=job_offer_id).first()
            if match:
                match.semantic_similarity = round(semantic_sim, 4)
                match.llm_score = llm_score
                match.compatibility_score = final_score
                match.matching_points = assessment.get("matching_points", [])
                match.gap_points = assessment.get("gap_points", [])
                match.summary = assessment.get("summary", "")
                match.skills_score = skills_score
                match.experience_score = experience_score
                match.seniority_score = seniority_score
                match.semantic_score = semantic_score
                match.certification_bonus = certification_bonus
                db.commit()
                db.refresh(match)
        return match
    
    @staticmethod
    def invalidate_cv_matches(cv_id: uuid.UUID, db: Session):
        """
        Invalidate all matches for a CV when CV data is updated.
        This ensures matches are recalculated with fresh data.
        """
        matches = db.query(Match).filter_by(cv_id=cv_id).all()
        for match in matches:
            db.delete(match)
        db.commit()
    
    @staticmethod
    def invalidate_job_matches(job_offer_id: uuid.UUID, db: Session):
        """
        Invalidate all matches for a job offer when job data is updated.
        This ensures matches are recalculated with fresh data.
        """
        matches = db.query(Match).filter_by(job_offer_id=job_offer_id).all()
        for match in matches:
            db.delete(match)
        db.commit()

    @staticmethod
    def get_best_matches_for_cv(
        cv_id: uuid.UUID,
        user_id: uuid.UUID,
        similarity_calculator: IEmbeddingSimilarityCalculator,
        llm_evaluator: ILLMMatchingEvaluator,
        db: Session,
        limit: int = 10,
        offset: int = 0
    ) -> List[Tuple[Match, JobOffer]]:
        """
        Find best matching job offers for a given CV, calculating top vector matches and returning ranked scores.
        Pre-filters by semantic similarity before calling LLM to avoid unnecessary API calls.
        """
        cv = db.get(CV, cv_id)
        if not cv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trouvé")

        # Security Check: Ownership verification
        if cv.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé : ce CV appartient à un autre utilisateur."
            )

        config = MatchingService.get_or_create_config(user_id, db)
        
        # Load user preferences for filtering (graceful degradation if not set)
        prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()

        # Retrieve top vector candidates using SQL pgvector (no artificial cut-off).
        # Semantic similarity is only one component of the 6-factor scoring, so we don't pre-filter.
        top_candidates = similarity_calculator.get_top_matching_job_offers(
            cv_id=cv_id,
            db=db,
            limit=limit * 3,  # Wider semantic candidate pool; existing matches reused for free
            threshold=0.0
        )

        # Cap new LLM evaluations per Discover request to avoid mass API usage.
        # Existing Match rows are reused without any LLM call.
        MAX_NEW_EVALUATIONS_PER_DISCOVER = 5
        new_evaluations = 0

        results = []
        for job_offer_id, sim_score in top_candidates:
            # Reuse existing match — no LLM call needed
            match = db.query(Match).filter_by(cv_id=cv_id, job_offer_id=job_offer_id).first()
            if not match:
                # Only evaluate if we haven't hit the per-request cap
                if new_evaluations >= MAX_NEW_EVALUATIONS_PER_DISCOVER:
                    continue
                try:
                    match = MatchingService.compute_match(
                        cv_id, job_offer_id, user_id, similarity_calculator, llm_evaluator, db
                    )
                    new_evaluations += 1
                except Exception as e:
                    db.rollback()
                    print(f"[MatchingService] Skipping candidate match error: {e}")
                    continue

            job_offer = db.get(JobOffer, job_offer_id)
            if match and job_offer:
                results.append((match, job_offer))

        # Sort descending by compatibility score
        results.sort(key=lambda x: x[0].compatibility_score, reverse=True)
        return results[offset : offset + limit]
