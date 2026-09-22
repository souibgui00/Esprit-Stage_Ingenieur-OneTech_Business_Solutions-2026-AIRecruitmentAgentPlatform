"""
Migration script to remove obsolete configuration fields from matching_configs table.

This migration removes the obsolete 2-factor architecture fields:
- threshold (obsolete, replaced by UserPreferences.min_match_score for auto-apply)
- semantic_weight (obsolete, 6-factor system uses fixed weights)
- llm_weight (obsolete, 6-factor system uses fixed weights)

This migration should be run within the Docker environment:
    docker-compose exec backend python migrations/remove_obsolete_matching_config_fields.py

Or run directly via docker-compose exec:
    docker-compose exec backend python -c "
import sys
sys.path.insert(0, '/app')
from migrations.remove_obsolete_matching_config_fields import migrate
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
    """Remove obsolete configuration fields from matching_configs table."""
    
    print("Starting migration: Remove obsolete fields from matching_configs table...")
    
    with engine.connect() as conn:
        # Check if columns exist
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'matching_configs' 
            AND column_name IN ('threshold', 'semantic_weight', 'llm_weight')
        """)
        existing_columns = conn.execute(check_query).fetchall()
        existing_column_names = [col[0] for col in existing_columns]
        
        print(f"Existing obsolete columns found: {existing_column_names}")
        
        # Remove obsolete columns
        if 'threshold' in existing_column_names:
            print("Removing threshold column...")
            conn.execute(text("ALTER TABLE matching_configs DROP COLUMN threshold"))
            conn.commit()
        
        if 'semantic_weight' in existing_column_names:
            print("Removing semantic_weight column...")
            conn.execute(text("ALTER TABLE matching_configs DROP COLUMN semantic_weight"))
            conn.commit()
        
        if 'llm_weight' in existing_column_names:
            print("Removing llm_weight column...")
            conn.execute(text("ALTER TABLE matching_configs DROP COLUMN llm_weight"))
            conn.commit()
        
        print("Migration completed successfully!")
        print("The matching_configs table now only contains:")
        print("  - id (UUID)")
        print("  - user_id (UUID)")
        print("  - (Reserved for future matching-related preferences)")
        print("\nThe 6-factor scoring system uses fixed weights:")
        print("  - Skills: 35 points")
        print("  - Experience: 20 points")
        print("  - Seniority: 10 points")
        print("  - Semantic: 15 points")
        print("  - LLM: 10 points")
        print("  - Certifications: 5 points")
        print("Application eligibility is controlled by UserPreferences.min_match_score")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)