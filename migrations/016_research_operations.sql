SET search_path TO tm2,pg_catalog;
CREATE TABLE research_operations (
    id uuid PRIMARY KEY,
    ordinal bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    project_id uuid NOT NULL REFERENCES projects(id),
    run_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    request_id uuid NOT NULL,
    fingerprint text NOT NULL,
    kind text NOT NULL,
    parameters jsonb NOT NULL,
    status text NOT NULL CHECK(status IN ('pending','completed','failed','interrupted')),
    checkpoint_id uuid NOT NULL,
    result_checkpoint_id uuid,
    job_id uuid REFERENCES jobs(id) ON DELETE SET NULL,
    result jsonb NOT NULL DEFAULT '{}',
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,request_id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id,checkpoint_id) REFERENCES checkpoints(project_id,run_id,id),
    FOREIGN KEY(project_id,run_id,result_checkpoint_id) REFERENCES checkpoints(project_id,run_id,id)
);
CREATE INDEX research_operations_page ON research_operations(run_id,ordinal DESC);
CREATE UNIQUE INDEX research_operation_active ON research_operations(run_id) WHERE status='pending';
ALTER TABLE research_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_operations FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON research_operations
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
INSERT INTO schema_version(version) VALUES(16);
