-- Add total_pages column to assessments table
-- Run this SQL in your PostgreSQL database

ALTER TABLE assessments ADD COLUMN IF NOT EXISTS total_pages FLOAT;

-- Verify the column was added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'assessments' AND column_name = 'total_pages';
