"""
Migration script to add HNSW index to cv_embeddings.vector for faster similarity search.

This migration adds an HNSW (Hierarchical Navigable Small World) index to the vector column
in the cv_embeddings table. This significantly improves performance of vector similarity queries
used in the matching pipeline.

The job_offer_embeddings table already has an HNSW index. This migration adds the same
to cv_embeddings for symmetry and performance.

This migration should be run within the Docker environment:
    docker-compose exec backend python migrations/add_hnsw_index_cv_embeddings.py

Or run directly via docker-compose exec:
    docker-compose exec backend python -c "
import sys
sys.path.insert(0, '/app')
from migrations.add_hnsw_index_cv_embeddings import migrate
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
    """Add HNSW index to cv_embeddings.vector column."""
    
    print("Starting migration: Add HNSW index to cv_embeddings.vector...")
    
    with engine.connect() as conn:
        # Check if index already exists
        check_query = text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'cv_embeddings'
            AND indexname = 'idx_cv_embeddings_vector_hnsw'
        """)
        existing_index = conn.execute(check_query).fetchone()
        
        if existing_index:
            print("HNSW index already exists on cv_embeddings.vector")
            print("Skipping migration...")
            return
        
        # Add HNSW index with cosine similarity operator class
        # vector_cosine_ops is the correct operator class for cosine similarity (<=> operator)
        print("Creating HNSW index on cv_embeddings.vector with vector_cosine_ops...")
        conn.execute(text("""
            CREATE INDEX idx_cv_embeddings_vector_hnsw 
            ON cv_embeddings 
            USING hnsw (vector vector_cosine_ops)
        """))
        conn.commit()
        
        print("Migration completed successfully!")
        print("Added HNSW index: idx_cv_embeddings_vector_hnsw")
        print("Operator class: vector_cosine_ops (for cosine similarity)")
        print("\nThis index will significantly improve performance of:")
        print("  - Vector similarity searches in the matching pipeline")
        print("  - Top-k job offer retrieval for CVs")
        print("\nNote: job_offer_embeddings already has an HNSW index:")
        print("  - idx_job_offer_embeddings_vector_hnsw")


def downgrade():
    """Remove HNSW index from cv_embeddings.vector column."""
    
    print("Starting downgrade: Remove HNSW index from cv_embeddings.vector...")
    
    with engine.connect() as conn:
        # Check if index exists
        check_query = text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'cv_embeddings'
            AND indexname = 'idx_cv_embeddings_vector_hnsw'
        """)
        existing_index = conn.execute(check_query).fetchone()
        
        if not existing_index:
            print("HNSW index does not exist on cv_embeddings.vector")
            print("Skipping downgrade...")
            return
        
        # Drop HNSW index
        print("Dropping HNSW index from cv_embeddings.vector...")
        conn.execute(text("DROP INDEX idx_cv_embeddings_vector_hnsw"))
        conn.commit()
        
        print("Downgrade completed successfully!")
        print("Removed HNSW index: idx_cv_embeddings_vector_hnsw")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add or remove HNSW index from cv_embeddings")
    parser.add_argument("--downgrade", action="store_true", help="Remove the HNSW index")
    args = parser.parse_args()
    
    try:
        if args.downgrade:
            downgrade()
        else:
            migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)