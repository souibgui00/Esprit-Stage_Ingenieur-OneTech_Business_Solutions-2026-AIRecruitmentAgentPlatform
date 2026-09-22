"""
⚠️  DANGEROUS: This script will DELETE ALL DATA in the database.
Use only for development/testing purposes.
Run with: python reset_database.py --confirm
"""
import sys
from sqlalchemy import text
from shared.database import engine

def reset_database():
    """Drop all tables and recreate them."""
    if "--confirm" not in sys.argv:
        print("⚠️  DANGER: This will DELETE ALL DATA in the database!")
        print("⚠️  To confirm, run: python reset_database.py --confirm")
        sys.exit(1)
    
    print("🔄 Resetting database...")
    
    with engine.connect() as connection:
        # Drop all tables in correct order (respecting foreign keys)
        connection.execute(text("DROP TABLE IF EXISTS notifications CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS user_auto_apply_settings CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS applications CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS user_activities CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS user_sessions CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS user_preferences CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS cvs CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS cv_skills CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS cv_embeddings CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS educations CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS experiences CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS personal_infos CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS job_offer_embeddings CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS job_skills CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS job_offers CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS collection_runs CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS job_sources CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS matches CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS matching_configs CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS skills CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        connection.commit()
    
    print("✅ All tables dropped. Run create_tables.py to recreate them.")

if __name__ == "__main__":
    reset_database()
