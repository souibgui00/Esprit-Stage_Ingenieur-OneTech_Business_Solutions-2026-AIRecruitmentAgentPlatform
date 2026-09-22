-- Migration: Add ON DELETE CASCADE to CV-related foreign keys
-- Date: 2025-01-18
-- Description: Adds CASCADE delete to 6 foreign keys that reference cvs table
--              This ensures that when a CV is deleted, all related data is automatically cleaned up.
--              Safe to run: No data loss, only constraint modification
--              Reversible: Manual rollback requires recreating constraints without CASCADE

-- Add CASCADE to experiences.cv_id
ALTER TABLE experiences 
DROP CONSTRAINT IF EXISTS experiences_cv_id_fkey;

ALTER TABLE experiences 
ADD CONSTRAINT experiences_cv_id_fkey 
FOREIGN KEY (cv_id) REFERENCES cvs(id) ON DELETE CASCADE;

-- Add CASCADE to educations.cv_id
ALTER TABLE educations 
DROP CONSTRAINT IF EXISTS educations_cv_id_fkey;

ALTER TABLE educations 
ADD CONSTRAINT educations_cv_id_fkey 
FOREIGN KEY (cv_id) REFERENCES cvs(id) ON DELETE CASCADE;

-- Add CASCADE to certifications.cv_id
ALTER TABLE certifications 
DROP CONSTRAINT IF EXISTS certifications_cv_id_fkey;

ALTER TABLE certifications 
ADD CONSTRAINT certifications_cv_id_fkey 
FOREIGN KEY (cv_id) REFERENCES cvs(id) ON DELETE CASCADE;

-- Add CASCADE to personal_infos.cv_id
ALTER TABLE personal_infos 
DROP CONSTRAINT IF EXISTS personal_infos_cv_id_fkey;

ALTER TABLE personal_infos 
ADD CONSTRAINT personal_infos_cv_id_fkey 
FOREIGN KEY (cv_id) REFERENCES cvs(id) ON DELETE CASCADE;

-- Add CASCADE to cv_embeddings.cv_id
ALTER TABLE cv_embeddings 
DROP CONSTRAINT IF EXISTS cv_embeddings_cv_id_fkey;

ALTER TABLE cv_embeddings 
ADD CONSTRAINT cv_embeddings_cv_id_fkey 
FOREIGN KEY (cv_id) REFERENCES cvs(id) ON DELETE CASCADE;

-- Add CASCADE to cv_skills.cv_id
ALTER TABLE cv_skills 
DROP CONSTRAINT IF EXISTS cv_skills_cv_id_fkey;

ALTER TABLE cv_skills 
ADD CONSTRAINT cv_skills_cv_id_fkey 
FOREIGN KEY (cv_id) REFERENCES cvs(id) ON DELETE CASCADE;
