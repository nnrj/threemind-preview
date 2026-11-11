ALTER TABLE tm2.input_frames ADD COLUMN source_policy jsonb
    CHECK(source_policy IS NULL OR jsonb_typeof(source_policy)='object');
INSERT INTO tm2.schema_version(version) VALUES(14);
