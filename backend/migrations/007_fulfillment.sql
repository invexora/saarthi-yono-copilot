ALTER TABLE recommendations ADD COLUMN execution_started_at REAL;
ALTER TABLE recommendations ADD COLUMN fulfillment_reference TEXT;
ALTER TABLE recommendations ADD COLUMN fulfilled_at REAL;
ALTER TABLE recommendations ADD COLUMN fulfillment_response_json TEXT;
