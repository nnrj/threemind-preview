SET search_path TO tm2,pg_catalog;
CREATE TABLE state_captures (
    id uuid PRIMARY KEY,
    ordinal bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    project_id uuid NOT NULL REFERENCES projects(id),
    run_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    request_id uuid NOT NULL,
    fingerprint text NOT NULL,
    parameters jsonb NOT NULL,
    command_id bigint NOT NULL REFERENCES commands(id),
    job_id uuid NOT NULL REFERENCES jobs(id),
    status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','failed')),
    checkpoint_id uuid,
    result jsonb NOT NULL DEFAULT '{}',
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE(project_id,request_id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id,checkpoint_id) REFERENCES checkpoints(project_id,run_id,id)
);
CREATE UNIQUE INDEX state_capture_pending ON state_captures(run_id) WHERE status='pending';
CREATE INDEX state_captures_page ON state_captures(run_id,ordinal DESC);
ALTER TABLE state_captures ENABLE ROW LEVEL SECURITY;
ALTER TABLE state_captures FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON state_captures
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
INSERT INTO schema_version(version) VALUES(22);
