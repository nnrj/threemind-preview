CREATE SCHEMA IF NOT EXISTS tm2;
SET search_path = tm2, pg_catalog;

CREATE TABLE schema_version (version integer PRIMARY KEY, installed_at timestamptz NOT NULL DEFAULT now());
INSERT INTO schema_version(version) VALUES(1);
CREATE TABLE users (
    id uuid PRIMARY KEY, username text NOT NULL UNIQUE, password_hash text,
    admin boolean NOT NULL DEFAULT false, enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
    token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf text NOT NULL, expires_at timestamptz NOT NULL
);
CREATE INDEX sessions_expiry ON sessions(expires_at);
CREATE TABLE login_attempts (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, username text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX login_attempts_window ON login_attempts(username,occurred_at);
CREATE TABLE projects (
    id uuid PRIMARY KEY, name text NOT NULL, owner_id uuid NOT NULL REFERENCES users(id),
    public boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE members (
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('owner','researcher','viewer')), PRIMARY KEY(project_id,user_id)
);
CREATE TABLE runs (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id), name text NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','paused','completed','failed','cancelled','dead','blocked')),
    life text NOT NULL DEFAULT 'waiting', spec jsonb NOT NULL, parent_id uuid REFERENCES runs(id),
    origin_hash text, state_hash text, revision bigint NOT NULL DEFAULT 0,
    time_us numeric(39,0) NOT NULL DEFAULT 0, sequence bigint NOT NULL DEFAULT 0,
    last_command bigint NOT NULL DEFAULT 0, metrics jsonb NOT NULL DEFAULT '{}', error text,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id)
);
CREATE INDEX runs_project_time ON runs(project_id,created_at DESC);
CREATE TABLE checkpoints (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, run_id uuid NOT NULL,
    revision bigint NOT NULL, time_us numeric(39,0) NOT NULL, sequence bigint NOT NULL,
    state_hash text NOT NULL, context jsonb NOT NULL DEFAULT '{}', byte_count bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(run_id,revision), UNIQUE(project_id,id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
CREATE TABLE state_chunks (
    project_id uuid NOT NULL, checkpoint_id uuid NOT NULL, ordinal integer NOT NULL,
    body bytea NOT NULL, sha256 text NOT NULL, PRIMARY KEY(checkpoint_id,ordinal),
    FOREIGN KEY(project_id,checkpoint_id) REFERENCES checkpoints(project_id,id) ON DELETE CASCADE
);
CREATE TABLE nodes (
    project_id uuid NOT NULL, run_id uuid NOT NULL, id bigint NOT NULL, channel bigint NOT NULL,
    activation double precision NOT NULL, inhibition double precision NOT NULL, trace double precision NOT NULL,
    support double precision NOT NULL, stability double precision NOT NULL,
    direct double precision NOT NULL, associative double precision NOT NULL,
    touches bigint NOT NULL, last_touch_us numeric(39,0) NOT NULL,
    PRIMARY KEY(run_id,id), FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
CREATE INDEX nodes_activation ON nodes(run_id,activation DESC,id);
CREATE TABLE edges (
    project_id uuid NOT NULL, run_id uuid NOT NULL, source bigint NOT NULL, target bigint NOT NULL,
    weight double precision NOT NULL, stability double precision NOT NULL, eligibility double precision NOT NULL,
    touches bigint NOT NULL, birth_us numeric(39,0) NOT NULL, last_touch_us numeric(39,0) NOT NULL,
    PRIMARY KEY(run_id,source,target), FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
CREATE INDEX edges_target ON edges(run_id,target,source);
CREATE INDEX edges_weight ON edges(run_id,weight DESC,source,target);
CREATE TABLE events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, project_id uuid NOT NULL, run_id uuid NOT NULL,
    event_key text NOT NULL, time_us numeric(39,0) NOT NULL, kind text NOT NULL, payload jsonb NOT NULL,
    UNIQUE(run_id,event_key), FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
CREATE INDEX events_timeline ON events(run_id,time_us,id);
CREATE TABLE observations (
    project_id uuid NOT NULL, run_id uuid NOT NULL, time_us numeric(39,0) NOT NULL,
    sequence bigint NOT NULL, metrics jsonb NOT NULL, quality text NOT NULL DEFAULT 'complete',
    PRIMARY KEY(run_id,time_us), FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
CREATE TABLE commands (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, project_id uuid NOT NULL, run_id uuid NOT NULL,
    kind text NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
CREATE INDEX commands_run ON commands(run_id,id);
CREATE TABLE jobs (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id), run_id uuid REFERENCES runs(id),
    kind text NOT NULL, params jsonb NOT NULL DEFAULT '{}', status text NOT NULL DEFAULT 'pending',
    worker_id text, generation bigint NOT NULL DEFAULT 0, attempts integer NOT NULL DEFAULT 0,
    lease_until timestamptz, result jsonb, error text, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id)
);
CREATE INDEX jobs_claim ON jobs(status,created_at);
CREATE UNIQUE INDEX jobs_one_run ON jobs(run_id) WHERE kind='run' AND status IN ('pending','leased');
CREATE TABLE workers (
    id text PRIMARY KEY, name text NOT NULL, token_hash text UNIQUE, enabled boolean NOT NULL DEFAULT true,
    heartbeat timestamptz, capabilities jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE artifacts (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, job_id uuid NOT NULL, name text NOT NULL,
    media_type text NOT NULL, bytes bigint NOT NULL, sha256 text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(project_id,id),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id) ON DELETE CASCADE
);
CREATE TABLE artifact_chunks (
    project_id uuid NOT NULL, artifact_id uuid NOT NULL, ordinal integer NOT NULL, body bytea NOT NULL,
    PRIMARY KEY(artifact_id,ordinal), FOREIGN KEY(project_id,artifact_id) REFERENCES artifacts(project_id,id) ON DELETE CASCADE
);
CREATE TABLE studies (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id), name text NOT NULL,
    protocol jsonb NOT NULL, protocol_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id uuid, action text NOT NULL,
    resource text, occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE outbox (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, project_id uuid NOT NULL, topic text NOT NULL,
    payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
-- Roles must be non-owner and non-superuser for these policies to protect requests.
-- Membership authorization is checked before setting the transaction's project context.
DO $$
DECLARE tab text;
BEGIN
    FOREACH tab IN ARRAY ARRAY['runs','checkpoints','state_chunks','nodes','edges','events','observations','commands','artifacts','artifact_chunks','studies'] LOOP
        EXECUTE format('ALTER TABLE tm2.%I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE tm2.%I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY project_boundary ON tm2.%I USING (project_id::text = current_setting(''tm.project_id'',true)) WITH CHECK (project_id::text = current_setting(''tm.project_id'',true))',tab);
    END LOOP;
END $$;
