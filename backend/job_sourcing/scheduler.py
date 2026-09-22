import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from shared.database import SessionLocal
from job_sourcing.models import JobSource
from job_sourcing.services.collection_service import JobCollectionService

logger = logging.getLogger("apscheduler")
scheduler = BackgroundScheduler()

def autonomous_job_sourcing_task():
    """Tâche périodique automatique exécutée par l'agent de recrutement."""
    logger.info("Agent autonome : démarrage de la collecte automatique périodique d'offres...")
    db = SessionLocal()
    try:
        active_sources = db.query(JobSource).filter_by(is_active=True).all()
        if not active_sources:
            logger.info("Agent autonome : aucune source active trouvée.")
            return

        # Mots-clés par défaut pour peupler la base de manière générale
        keywords = "developer python react javascript devops"
        
        for source in active_sources:
            try:
                logger.info(f"Agent autonome : collecte en cours pour la source '{source.name}'...")
                JobCollectionService.run_collection(source, keywords, db)
                logger.info(f"Agent autonome : collecte réussie pour '{source.name}'")
            except Exception as ex:
                logger.error(f"Agent autonome : erreur lors de la collecte de '{source.name}': {ex}")
    finally:
        db.close()
    logger.info("Agent autonome : collecte automatique terminée.")


def batch_match_evaluation_task():
    """
    Background task: progressively evaluate missing Match rows for all active users.

    For each user with a PARSED CV:
      1. Get top-50 semantic candidates via pgvector (prioritised by similarity).
      2. Skip any candidate that already has a Match row (no duplicate computation).
      3. Evaluate at most BATCH_SIZE_PER_USER new Matches per user per run.
      4. Persist each Match immediately; a single failure does NOT stop the batch.

    Runs every 30 minutes via APScheduler. No Celery / Redis required.
    """
    from cv_management.models import CV, CVStatus
    from matching.models import Match
    from matching.matching_service import MatchingService
    from matching.adapters.cosine_similarity_calculator import PgVectorSimilarityCalculator
    from matching.adapters.groq_matching_evaluator import GroqMatchingEvaluator

    BATCH_SIZE_PER_USER = 5  # Max new LLM evaluations per user per scheduler run
    SEMANTIC_POOL_SIZE  = 50  # Candidates retrieved via pgvector per user

    sim_calc = PgVectorSimilarityCalculator()
    llm_eval = GroqMatchingEvaluator()

    db = SessionLocal()
    try:
        parsed_cvs = db.query(CV).filter_by(status=CVStatus.PARSED).all()
        if not parsed_cvs:
            logger.info("[BatchMatch] No parsed CVs found — skipping run.")
            return

        logger.info(f"[BatchMatch] Starting batch evaluation for {len(parsed_cvs)} parsed CV(s).")

        for cv in parsed_cvs:
            try:
                top_candidates = sim_calc.get_top_matching_job_offers(
                    cv_id=cv.id, db=db, limit=SEMANTIC_POOL_SIZE, threshold=0.0
                )
            except Exception as e:
                logger.warning(f"[BatchMatch] Could not retrieve candidates for cv={cv.id}: {e}")
                continue

            # Find unscored candidates from top semantic pool and prioritize newly collected jobs
            from job_sourcing.models import JobOffer
            unscored_candidates = []
            for job_offer_id, sim_score in top_candidates:
                existing = db.query(Match.id).filter_by(
                    cv_id=cv.id, job_offer_id=job_offer_id
                ).first()
                if not existing:
                    job = db.get(JobOffer, job_offer_id)
                    col_time = job.collected_at if job else datetime.min
                    unscored_candidates.append((job_offer_id, sim_score, col_time))

            # Prioritize newest collected jobs first, then by semantic similarity
            unscored_candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)

            evaluated = 0
            for job_offer_id, _sim_score, _col_time in unscored_candidates:
                if evaluated >= BATCH_SIZE_PER_USER:
                    break

                try:
                    match = MatchingService.compute_match(
                        cv_id=cv.id,
                        job_offer_id=job_offer_id,
                        user_id=cv.user_id,
                        similarity_calculator=sim_calc,
                        llm_evaluator=llm_eval,
                        db=db,
                    )
                    evaluated += 1
                    logger.info(
                        f"[BatchMatch] Evaluated cv={cv.id} job={job_offer_id} "
                        f"({evaluated}/{BATCH_SIZE_PER_USER})"
                    )

                    # Trigger NEW_MATCH notification if score meets user threshold
                    try:
                        from user_management.models import UserPreferences
                        from notifications.services import NotificationService
                        from notifications.models import NotificationType
                        from job_sourcing.models import JobOffer

                        prefs = db.query(UserPreferences).filter_by(user_id=cv.user_id).first()
                        threshold = prefs.min_match_score if (prefs and prefs.min_match_score) else 80.0
                        if match.compatibility_score >= threshold:
                            job = db.get(JobOffer, job_offer_id)
                            job_title = job.title if job else "Nouvelle opportunité"
                            company = job.company if job else ""
                            comp_str = f" chez {company}" if company else ""
                            NotificationService.create_notification(
                                db=db,
                                user_id=cv.user_id,
                                type=NotificationType.NEW_MATCH,
                                message=f"Opportunité qualifiée trouvée : {job_title}{comp_str} (Score : {match.compatibility_score:.0f}%).",
                                send_email=False
                            )
                    except Exception as notif_err:
                        logger.warning(f"[BatchMatch] Notification creation failed (non-fatal): {notif_err}")

                except Exception as e:
                    db.rollback()
                    logger.warning(
                        f"[BatchMatch] Failed cv={cv.id} job={job_offer_id}: {e}"
                    )
                    continue

            logger.info(
                f"[BatchMatch] cv={cv.id}: {evaluated} new match(es) evaluated this run."
            )

    finally:
        db.close()
        logger.info("[BatchMatch] Batch evaluation run complete.")


def start_scheduler():
    """Démarre le scheduler en arrière-plan."""
    if not scheduler.running:
        # Job sourcing: collect new offers every 6 hours
        scheduler.add_job(
            autonomous_job_sourcing_task,
            trigger=IntervalTrigger(hours=6),
            id="autonomous_job_sourcing",
            name="Collecte automatique d'offres d'emploi par l'agent",
            replace_existing=True
        )
        # Match evaluation: progressively evaluate missing Match rows every 30 minutes
        scheduler.add_job(
            batch_match_evaluation_task,
            trigger=IntervalTrigger(minutes=30),
            id="batch_match_evaluation",
            name="Évaluation progressive des matchs manquants",
            replace_existing=True
        )
        scheduler.start()
        logger.info(
            "Agent autonome : Planificateur de tâches démarré "
            "(Collecte: toutes les 6h · Matchs: toutes les 30min)."
        )

def stop_scheduler():
    """Arrête proprement le scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Agent autonome : Planificateur de tâches arrêté.")
