SET search_path = tm2, pg_catalog;
CREATE TABLE input_envelopes (
    id uuid PRIMARY KEY, ordinal bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL REFERENCES runs(id),
    adapter_id text NOT NULL, adapter_version text NOT NULL, source text NOT NULL,
    actor_id uuid REFERENCES users(id), request_hash text NOT NULL,
    payload jsonb NOT NULL, payload_hash text NOT NULL, configuration jsonb NOT NULL, configuration_hash text NOT NULL,
    frame_count integer NOT NULL CHECK(frame_count >= 0), channel_count bigint NOT NULL CHECK(channel_count >= 0),
    delivered_count integer NOT NULL DEFAULT 0, filtered_count integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'accepted' CHECK(status IN ('accepted','scheduled','completed','rejected')),
    error text, command_id bigint, delay_us numeric(39,0) NOT NULL DEFAULT 0,
    requested_time_us numeric(39,0), last_delivery_us numeric(39,0),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX input_envelopes_run ON input_envelopes(run_id,ordinal);
CREATE INDEX input_envelopes_pending ON input_envelopes(run_id,status) WHERE status IN ('accepted','scheduled');
CREATE TABLE input_frames (
    project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL REFERENCES runs(id),
    envelope_id uuid NOT NULL REFERENCES input_envelopes(id), frame_index integer NOT NULL,
    core_event_id bigint, scheduled_time_us numeric(39,0) NOT NULL, delivered_time_us numeric(39,0),
    core_sequence bigint, stimulus jsonb NOT NULL, labels jsonb NOT NULL DEFAULT '{}',
    channel_count integer NOT NULL, status text NOT NULL CHECK(status IN ('scheduled','delivered','filtered')),
    reason text, scheduled_revision bigint NOT NULL, delivered_revision bigint,
    PRIMARY KEY (envelope_id,frame_index)
);
CREATE INDEX input_frames_pending ON input_frames(run_id,status,scheduled_time_us);
DO $$ BEGIN
    EXECUTE 'ALTER TABLE input_envelopes ENABLE ROW LEVEL SECURITY';
    EXECUTE 'ALTER TABLE input_envelopes FORCE ROW LEVEL SECURITY';
    EXECUTE 'ALTER TABLE input_frames ENABLE ROW LEVEL SECURITY';
    EXECUTE 'ALTER TABLE input_frames FORCE ROW LEVEL SECURITY';
END $$;
CREATE POLICY project_boundary ON input_envelopes
    USING(project_id::text=current_setting('tm.project_id',true)) WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE POLICY project_boundary ON input_frames
    USING(project_id::text=current_setting('tm.project_id',true)) WITH CHECK(project_id::text=current_setting('tm.project_id',true));
ALTER TABLE events ADD COLUMN commit_revision bigint, ADD COLUMN provenance jsonb;
INSERT INTO schema_version(version) VALUES(4);
