SET search_path = tm2, pg_catalog;
ALTER TABLE input_envelopes ADD COLUMN processed_revision bigint;
CREATE TABLE media_assets (
    project_id uuid NOT NULL REFERENCES projects(id), sha256 text NOT NULL,
    byte_length bigint NOT NULL CHECK(byte_length > 0), created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,sha256)
);
CREATE TABLE media_chunks (
    project_id uuid NOT NULL, sha256 text NOT NULL, chunk_index integer NOT NULL CHECK(chunk_index >= 0),
    body bytea NOT NULL CHECK(octet_length(body) <= 1048576),
    PRIMARY KEY(project_id,sha256,chunk_index),
    FOREIGN KEY(project_id,sha256) REFERENCES media_assets(project_id,sha256)
);
CREATE TABLE media_prepared_frames (
    project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL REFERENCES runs(id),
    envelope_id uuid NOT NULL REFERENCES input_envelopes(id), frame_index integer NOT NULL,
    stimulus jsonb NOT NULL, PRIMARY KEY(envelope_id,frame_index)
);
CREATE INDEX events_organ_output ON events(run_id,id DESC) WHERE kind='organ_output';
DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['media_assets','media_chunks','media_prepared_frames'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',t);
    END LOOP;
END $$;
INSERT INTO schema_version(version) VALUES(5);
