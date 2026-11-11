ALTER TABLE tm2.input_frames ADD COLUMN input_gate jsonb CHECK (input_gate IS NULL OR jsonb_typeof(input_gate)='object');
CREATE UNIQUE INDEX input_modulation_request ON tm2.commands(run_id,(payload->>'request_id'))
    WHERE kind='input_modulation';
INSERT INTO tm2.schema_version(version) VALUES(10);
