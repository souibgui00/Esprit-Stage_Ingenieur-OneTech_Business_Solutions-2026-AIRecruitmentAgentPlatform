"""
Migration script to add ON DELETE CASCADE to job_skills.skill_id foreign key.
This ensures that when a Skill is deleted, corresponding JobSkill records are also deleted.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from shared.database import engine


def add_job_skill_cascade():
    """Add ON DELETE CASCADE to job_skills.skill_id foreign key."""
    
    with engine.connect() as conn:
        # Check current constraint
        result = conn.execute(text("""
            SELECT confdeltype 
            FROM pg_constraint 
            JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
            JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
            WHERE pg_namespace.nspname = 'public'
            AND pg_class.relname = 'job_skills'
            AND conname = 'job_skills_skill_id_fkey'
        """)).fetchone()
        
        if result and result[0] == 'c':
            print("CASCADE already exists on job_skills.skill_id - no migration needed")
            return
        
        # Drop existing constraint
        print("Dropping existing job_skills_skill_id_fkey constraint...")
        conn.execute(text("""
            ALTER TABLE job_skills 
            DROP CONSTRAINT IF EXISTS job_skills_skill_id_fkey
        """))
        
        # Add constraint with CASCADE
        print("Adding job_skills_skill_id_fkey with ON DELETE CASCADE...")
        conn.execute(text("""
            ALTER TABLE job_skills 
            ADD CONSTRAINT job_skills_skill_id_fkey 
            FOREIGN KEY (skill_id) REFERENCES skills(id) 
            ON DELETE CASCADE
        """))
        
        conn.commit()
        
        # Verify the change
        result = conn.execute(text("""
            SELECT confdeltype 
            FROM pg_constraint 
            JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
            JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
            WHERE pg_namespace.nspname = 'public'
            AND pg_class.relname = 'job_skills'
            AND conname = 'job_skills_skill_id_fkey'
        """)).fetchone()
        
        if result and result[0] == 'c':
            print("✓ CASCADE successfully added to job_skills.skill_id")
        else:
            print("✗ Failed to add CASCADE to job_skills.skill_id")
            raise Exception("Migration verification failed")


if __name__ == "__main__":
    add_job_skill_cascade()
