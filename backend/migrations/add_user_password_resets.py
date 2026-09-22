"""
Migration script: add user_password_resets table.

Adds the table required for the forgot-password / reset-password flow.
Safe to run multiple times (uses CREATE TABLE IF NOT EXISTS).

Run inside the container:
    docker compose exec backend python migrations/add_user_password_resets.py
"""
import sys
sys.path.insert(0, '/app')

from sqlalchemy import text
from shared.database import engine


def upgrade():
    """Create user_password_resets table."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_password_resets (
                id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID        NOT NULL
                                REFERENCES users(id) ON DELETE CASCADE,
                token       VARCHAR(128) NOT NULL UNIQUE,
                created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
                expires_at  TIMESTAMP   NOT NULL,
                is_used     BOOLEAN     NOT NULL DEFAULT FALSE
            );
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_upr_user_id
                ON user_password_resets(user_id);
        """))

        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_upr_token
                ON user_password_resets(token);
        """))

        conn.commit()
    print("Migration completed: user_password_resets table created.")


def downgrade():
    """Drop user_password_resets table."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS user_password_resets CASCADE;"))
        conn.commit()
    print("Rollback completed: user_password_resets table dropped.")


if __name__ == "__main__":
    upgrade()
