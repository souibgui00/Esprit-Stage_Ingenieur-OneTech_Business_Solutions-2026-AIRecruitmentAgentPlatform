-- Migration: Migrate existing job offers to job_skills junction table
-- Date: 2025-01-18
-- Description: Parses existing required_skills JSON and creates JobSkill records
--              Uses cv_management.skill_normalization for canonical skill names
--              Safe to run: Can be re-run without data loss (checks for duplicates)
--              Reversible: DELETE FROM job_skills

-- Note: This SQL is a simplified version. For full normalization, use the Python script.
-- The Python script uses cv_management.skill_normalization.normalize_skill() which is not available in SQL.

-- For now, we'll use a simple lowercase normalization as a fallback
INSERT INTO job_skills (id, job_offer_id, skill_id, importance, created_at)
SELECT 
    gen_random_uuid() as id,
    jo.id as job_offer_id,
    s.id as skill_id,
    'essential' as importance,
    NOW() as created_at
FROM job_offers jo
CROSS JOIN LATERAL jsonb_array_elements_text(jsonb_path_query_array(jo.required_skills, '$')) AS skill_name
JOIN skills s ON s.canonical_name = LOWER(TRIM(skill_name))
WHERE jo.required_skills IS NOT NULL
AND jo.required_skills != ''
AND NOT EXISTS (
    SELECT 1 FROM job_skills js 
    WHERE js.job_offer_id = jo.id 
    AND js.skill_id = s.id
)
ON CONFLICT (job_offer_id, skill_id) DO NOTHING;
