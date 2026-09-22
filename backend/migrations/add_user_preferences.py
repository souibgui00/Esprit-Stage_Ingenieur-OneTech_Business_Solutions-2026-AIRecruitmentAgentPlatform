"""
Migration script to add user_preferences table for Phase 5.
Run this after applying the model changes.
"""
import sys
sys.path.insert(0, '/app')

from sqlalchemy import text
from shared.database import engine

def upgrade():
    """Add user_preferences table."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
                job_keywords TEXT DEFAULT 'developer python react javascript',
                preferred_locations TEXT[] DEFAULT ARRAY[]::TEXT[],
                preferred_contract_types TEXT[] DEFAULT ARRAY[]::TEXT[],
                remote_preference BOOLEAN DEFAULT true,
                min_salary INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);
        """))
        
        conn.commit()
    print("Migration completed: user_preferences table created")

def downgrade():
    """Remove user_preferences table."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS user_preferences CASCADE;"))
        conn.commit()
    print("Rollback completed: user_preferences table dropped")

if __name__ == "__main__":
    upgrade()
