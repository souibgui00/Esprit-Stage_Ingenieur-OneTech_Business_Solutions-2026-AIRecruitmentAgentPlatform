"""
Migration script to add 6-factor scoring fields to matches table.

This migration should be run within the Docker environment:
    docker-compose exec backend python migrations/add_6factor_scoring_fields.py

Or run directly via docker-compose exec:
    docker-compose exec backend python -c "
import sys
sys.path.insert(0, '/app')
from migrations.add_6factor_scoring_fields import migrate
migrate()
"
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from shared.database import engine


def migrate():
    """Add new 6-factor scoring fields to matches table."""
    
    print("Starting migration: Add 6-factor scoring fields to matches table...")
    
    with engine.connect() as conn:
        # Check if columns already exist
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'matches' 
            AND column_name IN ('skills_score', 'experience_score', 'seniority_score', 'semantic_score', 'certification_bonus')
        """)
        existing_columns = conn.execute(check_query).fetchall()
        existing_column_names = [col[0] for col in existing_columns]
        
        print(f"Existing columns found: {existing_column_names}")
        
        # Add missing columns
        if 'skills_score' not in existing_column_names:
            print("Adding skills_score column...")
            conn.execute(text("ALTER TABLE matches ADD COLUMN skills_score FLOAT DEFAULT 0.0"))
            conn.commit()
        
        if 'experience_score' not in existing_column_names:
            print("Adding experience_score column...")
            conn.execute(text("ALTER TABLE matches ADD COLUMN experience_score FLOAT DEFAULT 0.0"))
            conn.commit()
        
        if 'seniority_score' not in existing_column_names:
            print("Adding seniority_score column...")
            conn.execute(text("ALTER TABLE matches ADD COLUMN seniority_score FLOAT DEFAULT 0.0"))
            conn.commit()
        
        if 'semantic_score' not in existing_column_names:
            print("Adding semantic_score column...")
            conn.execute(text("ALTER TABLE matches ADD COLUMN semantic_score FLOAT DEFAULT 0.0"))
            conn.commit()
        
        if 'certification_bonus' not in existing_column_names:
            print("Adding certification_bonus column...")
            conn.execute(text("ALTER TABLE matches ADD COLUMN certification_bonus FLOAT DEFAULT 0.0"))
            conn.commit()
        
        # Update llm_score description (changing from 0-100 to 0-10)
        print("Note: llm_score now represents 0-10 range instead of 0-100")
        
        print("Migration completed successfully!")
        print("New schema includes:")
        print("  - skills_score (0.0 to 35.0)")
        print("  - experience_score (0.0 to 20.0)")
        print("  - seniority_score (0.0 to 10.0)")
        print("  - semantic_score (0.0 to 15.0)")
        print("  - certification_bonus (0.0 to 5.0)")
        print("  - llm_score (now 0.0 to 10.0, was 0.0 to 100.0)")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)