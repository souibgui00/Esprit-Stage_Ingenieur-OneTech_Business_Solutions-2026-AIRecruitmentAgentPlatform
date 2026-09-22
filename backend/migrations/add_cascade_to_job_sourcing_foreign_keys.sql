-- Migration: Add ON DELETE CASCADE to Job Sourcing foreign keys
-- Date: 2025-01-18
-- Description: Adds CASCADE delete to 3 foreign keys in job_sourcing module
--              This ensures that when a JobSource is deleted, all related JobOffers and CollectionRuns are automatically cleaned up.
--              When a JobOffer is deleted, its JobOfferEmbedding is automatically cleaned up.
--              Safe to run: No data loss, only constraint modification
--              Reversible: Manual rollback requires recreating constraints without CASCADE

-- Add CASCADE to job_offers.source_id
ALTER TABLE job_offers 
DROP CONSTRAINT job_offers_source_id_fkey;

ALTER TABLE job_offers 
ADD CONSTRAINT job_offers_source_id_fkey 
FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE CASCADE;

-- Add CASCADE to job_offer_embeddings.job_offer_id
ALTER TABLE job_offer_embeddings 
DROP CONSTRAINT job_offer_embeddings_job_offer_id_fkey;

ALTER TABLE job_offer_embeddings 
ADD CONSTRAINT job_offer_embeddings_job_offer_id_fkey 
FOREIGN KEY (job_offer_id) REFERENCES job_offers(id) ON DELETE CASCADE;

-- Add CASCADE to collection_runs.source_id
ALTER TABLE collection_runs 
DROP CONSTRAINT collection_runs_source_id_fkey;

ALTER TABLE collection_runs 
ADD CONSTRAINT collection_runs_source_id_fkey 
FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE CASCADE;
