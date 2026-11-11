SET search_path = tm2, pg_catalog;

CREATE TABLE device_bindings (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL REFERENCES runs(id),
    name text NOT NULL, issuer_id uuid NOT NULL REFERENCES users(id),
    token_hash text NOT NULL, token_generation integer NOT NULL DEFAULT 1,
    enabled boolean NOT NULL DEFAULT true, configuration jsonb NOT NULL,
    rate_window timestamptz NOT NULL DEFAULT now(), rate_count integer NOT NULL DEFAULT 0,
    expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,run_id,id), FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id)
);
CREATE INDEX device_bindings_run ON device_bindings(run_id,created_at,id);

CREATE TABLE device_sessions (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL REFERENCES runs(id),
    device_id uuid NOT NULL REFERENCES device_bindings(id), token_generation integer NOT NULL,
    clock_mode text NOT NULL CHECK(clock_mode IN ('device','simulation')), source_clock jsonb NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','closed','interrupted','revoked')),
    next_sequence bigint NOT NULL DEFAULT 0, last_capture_us numeric(39,0), last_frame_us numeric(39,0),
    origin_sim_us numeric(39,0), reason text, byte_count bigint NOT NULL DEFAULT 0,
    rate_window timestamptz NOT NULL DEFAULT now(), rate_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,run_id,id), FOREIGN KEY(project_id,run_id,device_id) REFERENCES device_bindings(project_id,run_id,id)
);
CREATE INDEX device_sessions_run ON device_sessions(run_id,device_id,created_at,id);
CREATE INDEX device_sessions_active ON device_sessions(device_id,status);

CREATE TABLE device_packets (
    project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL REFERENCES runs(id),
    session_id uuid NOT NULL REFERENCES device_sessions(id), sequence bigint NOT NULL,
    kind text NOT NULL, sha256 text NOT NULL, receipt jsonb NOT NULL,
    envelope_id uuid REFERENCES input_envelopes(id), command_id bigint REFERENCES commands(id),
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(session_id,sequence),
    FOREIGN KEY(project_id,run_id,session_id) REFERENCES device_sessions(project_id,run_id,id)
);
CREATE INDEX device_packets_run ON device_packets(run_id,created_at);

ALTER TABLE device_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE device_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE device_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_packets FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON device_bindings USING(project_id::text=current_setting('tm.project_id',true)) WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE POLICY project_boundary ON device_sessions USING(project_id::text=current_setting('tm.project_id',true)) WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE POLICY project_boundary ON device_packets USING(project_id::text=current_setting('tm.project_id',true)) WITH CHECK(project_id::text=current_setting('tm.project_id',true));
INSERT INTO schema_version(version) VALUES(11);
