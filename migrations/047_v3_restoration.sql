SET search_path = tm2, pg_catalog;
-- Nullable for historical projections: absent history is never invented.
-- Existing checkpoint blobs and test runs are not converted or resumed.
ALTER TABLE nodes ADD COLUMN birth_us numeric(39,0);
ALTER TABLE nodes ADD COLUMN local_plasticity double precision;
ALTER TABLE nodes ADD COLUMN pending_inhibition double precision;
ALTER TABLE nodes ADD COLUMN generated_inhibition double precision;
INSERT INTO schema_version(version) VALUES(47);
