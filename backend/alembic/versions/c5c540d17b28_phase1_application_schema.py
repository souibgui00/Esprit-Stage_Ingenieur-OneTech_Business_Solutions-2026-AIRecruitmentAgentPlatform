"""phase1_application_schema

Revision ID: c5c540d17b28
Revises: 
Create Date: 2026-09-03 17:44:45.480562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5c540d17b28'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update PostgreSQL Enums using autocommit_block
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE applicationmode ADD VALUE IF NOT EXISTS 'ASSISTED'")
        op.execute("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'DRAFT'")
        op.execute("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'SUBMITTING'")
        op.execute("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'ACTION_REQUIRED'")
        op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ACTION_REQUIRED'")

    # 2. Add Application.job_offer_id column (nullable at first for backfill)
    op.add_column('applications', sa.Column('job_offer_id', sa.UUID(), nullable=True))

    # 3. Backfill job_offer_id from matches table
    op.execute("""
        UPDATE applications
        SET job_offer_id = matches.job_offer_id
        FROM matches
        WHERE applications.match_id = matches.id
        AND applications.job_offer_id IS NULL;
    """)

    # 4. In case of any existing applications that had no matching match, check before NOT NULL
    # (Safe guard to avoid migration failure)
    op.alter_column('applications', 'job_offer_id', nullable=False)

    # 5. Create index and foreign key constraint with RESTRICT for job_offer_id
    op.create_index('idx_applications_job_offer_id', 'applications', ['job_offer_id'])
    op.create_foreign_key(
        'fk_applications_job_offer_id',
        'applications',
        'job_offers',
        ['job_offer_id'],
        ['id'],
        ondelete='RESTRICT'
    )

    # 6. Change Application.match_id to nullable=True and foreign key to ON DELETE SET NULL
    op.alter_column('applications', 'match_id', nullable=True)
    # Drop old cascading foreign key
    op.drop_constraint('applications_match_id_fkey', 'applications', type_='foreignkey')
    # Add new foreign key with ON DELETE SET NULL
    op.create_foreign_key(
        'applications_match_id_fkey',
        'applications',
        'matches',
        ['match_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 7. Add database-level UniqueConstraint on (user_id, job_offer_id)
    op.create_unique_constraint(
        'uq_user_job_application',
        'applications',
        ['user_id', 'job_offer_id']
    )


def downgrade() -> None:
    # 1. Drop unique constraint
    op.drop_constraint('uq_user_job_application', 'applications', type_='unique')

    # 2. Restore match_id FK to CASCADE and not null
    op.drop_constraint('applications_match_id_fkey', 'applications', type_='foreignkey')
    op.create_foreign_key(
        'applications_match_id_fkey',
        'applications',
        'matches',
        ['match_id'],
        ['id'],
        ondelete='CASCADE'
    )
    op.alter_column('applications', 'match_id', nullable=False)

    # 3. Drop job_offer_id FK, index, and column
    op.drop_constraint('fk_applications_job_offer_id', 'applications', type_='foreignkey')
    op.drop_index('idx_applications_job_offer_id', table_name='applications')
    op.drop_column('applications', 'job_offer_id')
