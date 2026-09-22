-- Migration: Create job_skills junction table for normalized job skills
-- Date: 2025-01-18
-- Description: Creates a junction table to link JobOffers with Skills using canonical skill names
--              This enables consistent skill normalization between CVs and Jobs
--              Safe to run: Creates new table, no data loss
--              Reversible: DROP TABLE job_skills

CREATE TABLE job_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_offer_id UUID NOT NULL REFERENCES job_offers(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES skills(id),
    importance VARCHAR(20) DEFAULT 'essential',
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_job_offer_skill UNIQUE (job_offer_id, skill_id)
);

-- Create index on skill_id for skill-based queries
CREATE INDEX idx_job_skills_skill_id ON job_skills(skill_id);

-- Create index on job_offer_id for efficient deletion
CREATE INDEX idx_job_skills_job_offer_id ON job_skills(job_offer_id);
