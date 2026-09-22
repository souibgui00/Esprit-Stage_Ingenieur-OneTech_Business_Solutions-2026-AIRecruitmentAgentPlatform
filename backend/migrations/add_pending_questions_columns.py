"""
Migration script to add pending_questions and user_responses columns to applications table.
Run this manually since alembic is not available in the environment.
"""
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.database import engine
from sqlalchemy import text

def add_columns():
    """Add pending_questions and user_responses columns to applications table."""
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'applications' 
            AND column_name IN ('pending_questions', 'user_responses')
        """))
        existing_columns = [row[0] for row in result]
        
        if 'pending_questions' not in existing_columns:
            print("Adding pending_questions column...")
            conn.execute(text("""
                ALTER TABLE applications 
                ADD COLUMN pending_questions JSON
            """))
            conn.commit()
            print("✓ pending_questions column added")
        else:
            print("✓ pending_questions column already exists")
        
        if 'user_responses' not in existing_columns:
            print("Adding user_responses column...")
            conn.execute(text("""
                ALTER TABLE applications 
                ADD COLUMN user_responses JSON
            """))
            conn.commit()
            print("✓ user_responses column added")
        else:
            print("✓ user_responses column already exists")
        
        print("\nMigration completed successfully!")

if __name__ == "__main__":
    add_columns()
