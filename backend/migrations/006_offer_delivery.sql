ALTER TABLE recommendations ADD COLUMN evidence_json TEXT;
ALTER TABLE recommendations ADD COLUMN presented_at REAL;

UPDATE recommendations
SET status = 'presented', presented_at = created_at
WHERE status = 'pending';
