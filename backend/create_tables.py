from sqlalchemy import text
import sys

from shared.database import engine
from cv_management.models import Base
from user_management.models import User, UserSession, UserActivity
from job_sourcing.models import JobSource, JobOffer, JobOfferEmbedding, CollectionRun, JobSkill
from matching.models import Match, MatchingConfig
from applications.models import Application, UserAutoApplySettings
from notifications.models import Notification

# SAFETY CHECK: Prevent accidental data loss
with engine.connect() as connection:
    # Check if users table exists and has data
    try:
        result = connection.execute(text("SELECT COUNT(*) FROM users")).fetchone()
        user_count = result[0] if result else 0
        
        if user_count > 0:
            print(f"⚠️  WARNING: Database already contains {user_count} user(s).")
            print("⚠️  Running this script again is unnecessary and may cause issues.")
            print("⚠️  If you want to reset the database, use a dedicated reset script instead.")
            response = input("Continue anyway? (type 'yes' to confirm): ")
            if response.lower() != 'yes':
                print("Aborted. No changes made.")
                sys.exit(0)
    except Exception:
        # Table doesn't exist yet, safe to proceed
        pass

with engine.connect() as connection:
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    connection.commit()

Base.metadata.create_all(engine)

# Create HNSW index for vector similarity search
with engine.connect() as connection:
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_job_offer_embeddings_vector_hnsw
        ON job_offer_embeddings
        USING hnsw (vector vector_cosine_ops)
    """))
    connection.commit()

print("Tables créées avec succès.")