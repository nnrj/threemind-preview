SET search_path TO tm2,pg_catalog;
CREATE TABLE research_plans (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    run_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    request_id uuid NOT NULL,
    fingerprint text NOT NULL,
    name text NOT NULL,
    protocol jsonb NOT NULL,
    protocol_hash text NOT NULL,
    origin text NOT NULL CHECK(origin IN ('human','ai')),
    status text NOT NULL DEFAULT 'ready' CHECK(status IN ('ready','queued','running','paused','completed','failed','cancelled')),
    next_step integer NOT NULL DEFAULT 0,
    step_attempt integer NOT NULL DEFAULT 0,
    wait_target_us numeric(39,0),
    expected_revision bigint NOT NULL,
    expected_command bigint NOT NULL,
    checkpoint_id uuid NOT NULL,
    job_id uuid REFERENCES jobs(id) ON DELETE SET NULL,
    stop_requested boolean NOT NULL DEFAULT false,
    cancel_requested boolean NOT NULL DEFAULT false,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,request_id),
    UNIQUE(project_id,run_id,id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id,checkpoint_id) REFERENCES checkpoints(project_id,run_id,id)
);
CREATE INDEX research_plans_page ON research_plans(run_id,created_at DESC,id);
CREATE UNIQUE INDEX research_plan_active ON research_plans(run_id) WHERE status IN ('queued','running');
ALTER TABLE research_operations ADD COLUMN plan_id uuid;
ALTER TABLE research_operations ADD COLUMN plan_step integer;
ALTER TABLE research_operations ADD COLUMN plan_attempt integer NOT NULL DEFAULT 0;
ALTER TABLE research_operations ADD CONSTRAINT research_operation_plan
    FOREIGN KEY(project_id,run_id,plan_id) REFERENCES research_plans(project_id,run_id,id);
CREATE UNIQUE INDEX research_operation_step ON research_operations(plan_id,plan_step,plan_attempt) WHERE plan_step IS NOT NULL;
ALTER TABLE research_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_plans FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON research_plans
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
INSERT INTO schema_version(version) VALUES(17);
