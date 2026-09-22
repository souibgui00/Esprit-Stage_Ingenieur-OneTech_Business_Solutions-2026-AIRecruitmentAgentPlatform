-- Migration: Add 6-factor scoring fields to matches table
-- This adds the new scoring fields for the 6-factor architecture

-- Add skills_score column (0.0 to 35.0)
ALTER TABLE matches 
ADD COLUMN IF NOT EXISTS skills_score FLOAT DEFAULT 0.0;

-- Add experience_score column (0.0 to 20.0)
ALTER TABLE matches 
ADD COLUMN IF NOT EXISTS experience_score FLOAT DEFAULT 0.0;

-- Add seniority_score column (0.0 to 10.0)
ALTER TABLE matches 
ADD COLUMN IF NOT EXISTS seniority_score FLOAT DEFAULT 0.0;

-- Add semantic_score column (0.0 to 15.0)
ALTER TABLE matches 
ADD COLUMN IF NOT EXISTS semantic_score FLOAT DEFAULT 0.0;

-- Add certification_bonus column (0.0 to 5.0)
ALTER TABLE matches 
ADD COLUMN IF NOT EXISTS certification_bonus FLOAT DEFAULT 0.0;

-- Note: llm_score still exists but now represents 0-10 range instead of 0-100
-- The application layer will handle the normalization