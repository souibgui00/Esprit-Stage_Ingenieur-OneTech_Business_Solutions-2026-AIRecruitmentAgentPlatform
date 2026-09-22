"""
Migration script to add certification structures for structured certification tracking.

This migration adds:
1. certification_standards table (for canonical name mapping)
2. required_certifications and preferred_certifications columns to job_offers
3. Seed data with 10-15 verified common certifications

This migration performs schema changes + static seed data only.
It does NOT inspect, normalize, or modify existing job offers.
Existing jobs will be processed by a separate CertificationBackfillService.

This migration should be run within the Docker environment:
    docker-compose exec backend python migrations/add_certification_structures.py

Or run directly via docker-compose exec:
    docker-compose exec backend python -c "
import sys
sys.path.insert(0, '/app')
from migrations.add_certification_structures import migrate
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
    """Add certification structures to database."""
    
    print("Starting migration: Add certification structures...")
    
    with engine.connect() as conn:
        # Step 1: Create certification_standards table
        print("\nStep 1: Creating certification_standards table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS certification_standards (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                canonical_name VARCHAR(200) UNIQUE NOT NULL,
                aliases TEXT[] NOT NULL,
                category VARCHAR(50) NOT NULL,
                description VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        print("✓ certification_standards table created")
        
        # Step 2: Seed with verified certifications
        print("\nStep 2: Seeding certification_standards with verified certifications...")
        
        certifications = [
            # Cloud certifications (4)
            {
                "canonical": "AWS Certified Solutions Architect",
                "aliases": ["AWS Solutions Architect", "AWS CSA", "AWS Solutions Architect Certification", "aws solutions architect"],
                "category": "cloud",
                "description": "AWS Certified Solutions Architect - Professional cloud architect certification"
            },
            {
                "canonical": "AWS Certified Developer",
                "aliases": ["AWS Developer Associate", "AWS Developer Certification", "aws certified developer"],
                "category": "cloud",
                "description": "AWS Certified Developer - Associate level AWS certification"
            },
            {
                "canonical": "Azure Solutions Architect",
                "aliases": ["Azure Solutions Architect Expert", "Microsoft Azure Solutions Architect", "azure solutions architect"],
                "category": "cloud",
                "description": "Azure Solutions Architect - Microsoft Azure cloud architect certification"
            },
            {
                "canonical": "GCP Professional Cloud Architect",
                "aliases": ["Google Cloud Professional Cloud Architect", "GCP Cloud Architect", "gcp professional cloud architect"],
                "category": "cloud",
                "description": "GCP Professional Cloud Architect - Google Cloud certification"
            },
            # Security certifications (3)
            {
                "canonical": "CISSP",
                "aliases": ["Certified Information Systems Security Professional", "cissp"],
                "category": "security",
                "description": "CISSP - Information systems security certification"
            },
            {
                "canonical": "CISA",
                "aliases": ["Certified Information Systems Auditor", "cisa"],
                "category": "security",
                "description": "CISA - Information systems audit certification"
            },
            {
                "canonical": "CISM",
                "aliases": ["Certified Information Security Manager", "cism"],
                "category": "security",
                "description": "CISM - Information security management certification"
            },
            # Project management certifications (3)
            {
                "canonical": "PMP",
                "aliases": ["Project Management Professional", "PMP Certification", "pmp"],
                "category": "project_management",
                "description": "PMP - Project management professional certification"
            },
            {
                "canonical": "PRINCE2",
                "aliases": ["PRINCE2 Practitioner", "PRINCE2 Foundation", "prince2"],
                "category": "project_management",
                "description": "PRINCE2 - Project management methodology certification"
            },
            {
                "canonical": "Scrum Master",
                "aliases": ["Certified Scrum Master", "CSM", "PSM", "scrum master"],
                "category": "project_management",
                "description": "Scrum Master - Agile project management certification"
            },
            # AI/ML certifications (3)
            {
                "canonical": "NVIDIA Deep Learning Institute Certificate",
                "aliases": ["NVIDIA DLI", "Deep Learning Institute Certificate", "DLI Certificate", "nvidia deep learning institute"],
                "category": "ai_ml",
                "description": "NVIDIA Deep Learning Institute Certificate - AI/ML certification"
            },
            {
                "canonical": "TensorFlow Developer Certificate",
                "aliases": ["TensorFlow Developer", "TF Developer Certificate", "TensorFlow Certified", "tensorflow developer certificate"],
                "category": "ai_ml",
                "description": "TensorFlow Developer Certificate - TensorFlow framework certification"
            },
            {
                "canonical": "AWS Machine Learning Specialty",
                "aliases": ["AWS ML Specialty", "AWS Machine Learning Certification", "aws machine learning specialty"],
                "category": "ai_ml",
                "description": "AWS Machine Learning Specialty - AWS ML certification"
            },
            # Networking certifications (2)
            {
                "canonical": "CCNA",
                "aliases": ["Cisco Certified Network Associate", "Cisco CCNA", "ccna"],
                "category": "networking",
                "description": "CCNA - Cisco network associate certification"
            },
            {
                "canonical": "CCNP",
                "aliases": ["Cisco Certified Network Professional", "Cisco CCNP", "ccnp"],
                "category": "networking",
                "description": "CCNP - Cisco network professional certification"
            }
        ]
        
        for cert in certifications:
            # Check if already exists
            check_query = text("""
                SELECT id FROM certification_standards WHERE canonical_name = :canonical_name
            """)
            existing = conn.execute(check_query, {"canonical_name": cert["canonical"]}).fetchone()
            
            if not existing:
                conn.execute(text("""
                    INSERT INTO certification_standards (canonical_name, aliases, category, description)
                    VALUES (:canonical_name, :aliases, :category, :description)
                """), {
                    "canonical_name": cert["canonical"],
                    "aliases": cert["aliases"],
                    "category": cert["category"],
                    "description": cert["description"]
                })
                conn.commit()
                print(f"  ✓ Added: {cert['canonical']}")
            else:
                print(f"  - Already exists: {cert['canonical']}")
        
        print(f"✓ Seeded {len(certifications)} certifications")
        
        # Step 3: Add columns to job_offers
        print("\nStep 3: Adding certification columns to job_offers...")
        
        # Check if columns already exist
        check_columns_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'job_offers' 
            AND column_name IN ('required_certifications', 'preferred_certifications')
        """)
        existing_columns = conn.execute(check_columns_query).fetchall()
        existing_column_names = [col[0] for col in existing_columns]
        
        if 'required_certifications' not in existing_column_names:
            conn.execute(text("ALTER TABLE job_offers ADD COLUMN required_certifications TEXT[] DEFAULT '{}'"))
            conn.commit()
            print("  ✓ Added required_certifications column")
        else:
            print("  - required_certifications column already exists")
        
        if 'preferred_certifications' not in existing_column_names:
            conn.execute(text("ALTER TABLE job_offers ADD COLUMN preferred_certifications TEXT[] DEFAULT '{}'"))
            conn.commit()
            print("  ✓ Added preferred_certifications column")
        else:
            print("  - preferred_certifications column already exists")
        
        print("\nMigration completed successfully!")
        print("\nDatabase schema now includes:")
        print("  - certification_standards table (with 15 verified certifications)")
        print("  - job_offers.required_certifications (TEXT array)")
        print("  - job_offers.preferred_certifications (TEXT array)")
        print("\nNext steps:")
        print("  1. Implement certification extraction in JobNormalizationService")
        print("  2. Implement CertificationBackfillService for existing 206 jobs")
        print("  3. Update calculate_certification_bonus() to use structured fields")
        print("  4. Run sample backfill (10 jobs) for testing")
        print("  5. Run full backfill (206 jobs)")
        print("  6. Verify certification bonus calculation")


def downgrade():
    """Remove certification structures from database."""
    
    print("Starting downgrade: Remove certification structures...")
    
    with engine.connect() as conn:
        # Drop columns from job_offers
        print("\nStep 1: Dropping certification columns from job_offers...")
        
        check_columns_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'job_offers' 
            AND column_name IN ('required_certifications', 'preferred_certifications')
        """)
        existing_columns = conn.execute(check_columns_query).fetchall()
        existing_column_names = [col[0] for col in existing_columns]
        
        if 'required_certifications' in existing_column_names:
            conn.execute(text("ALTER TABLE job_offers DROP COLUMN required_certifications"))
            conn.commit()
            print("  ✓ Dropped required_certifications column")
        else:
            print("  - required_certifications column does not exist")
        
        if 'preferred_certifications' in existing_column_names:
            conn.execute(text("ALTER TABLE job_offers DROP COLUMN preferred_certifications"))
            conn.commit()
            print("  ✓ Dropped preferred_certifications column")
        else:
            print("  - preferred_certifications column does not exist")
        
        # Drop certification_standards table
        print("\nStep 2: Dropping certification_standards table...")
        conn.execute(text("DROP TABLE IF EXISTS certification_standards"))
        conn.commit()
        print("  ✓ Dropped certification_standards table")
        
        print("\nDowngrade completed successfully!")
        print("\nRestored state:")
        print("  - certification_standards table removed")
        print("  - job_offers certification columns removed")
        print("  - Old certification extraction logic in scoring_service.py will be restored")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add or remove certification structures")
    parser.add_argument("--downgrade", action="store_true", help="Remove the certification structures")
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