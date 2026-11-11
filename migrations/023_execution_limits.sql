SET search_path TO tm2,pg_catalog;
CREATE TABLE execution_limits (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    revision bigint NOT NULL DEFAULT 1 CHECK(revision > 0),
    limits jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE project_execution_limits (
    project_id uuid PRIMARY KEY REFERENCES projects(id),
    revision bigint NOT NULL CHECK(revision > 0),
    limits jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE execution_limit_history (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id uuid REFERENCES projects(id),
    revision bigint NOT NULL,
    limits jsonb NOT NULL,
    actor_id uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX execution_limit_history_scope ON execution_limit_history(project_id,id DESC);
CREATE INDEX jobs_project_queue_active ON jobs(project_id,kind,lease_until) WHERE status IN ('pending','leased');
INSERT INTO schema_version(version) VALUES(23);
