SET search_path = tm2, pg_catalog;
CREATE TABLE capture_sessions (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id), name text NOT NULL,
    kind text NOT NULL CHECK(kind IN ('audio','video','av')),
    status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','stopped','interrupted')),
    configuration jsonb NOT NULL, source_clock jsonb NOT NULL, encoder_state jsonb NOT NULL,
    next_sequence bigint NOT NULL DEFAULT 0 CHECK(next_sequence BETWEEN 0 AND 4294967296),
    byte_count bigint NOT NULL DEFAULT 0 CHECK(byte_count >= 0),
    last_capture_us numeric(30,0), origin_sim_us numeric(30,0), reason text,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id)
);
CREATE INDEX capture_session_page ON capture_sessions(run_id,created_at DESC,id);
CREATE UNIQUE INDEX capture_one_active ON capture_sessions(run_id) WHERE status='active';
CREATE TABLE capture_packets (
    project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL,
    session_id uuid NOT NULL REFERENCES capture_sessions(id), sequence bigint NOT NULL CHECK(sequence>=0),
    envelope_id uuid NOT NULL REFERENCES input_envelopes(id), sha256 text NOT NULL, metadata jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(session_id,sequence),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,sha256) REFERENCES media_assets(project_id,sha256)
);
CREATE INDEX capture_packet_run ON capture_packets(run_id,session_id,sequence);
DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['capture_sessions','capture_packets'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',t);
    END LOOP;
END $$;
INSERT INTO schema_version(version) VALUES(8);
