SET search_path TO tm2,pg_catalog;
-- Old rows keep unknown provenance; do not guess their original commit.
ALTER TABLE observations ADD COLUMN commit_revision bigint;
CREATE INDEX ai_calls_run_page ON ai_calls(run_id,purpose,ordinal DESC);

CREATE TABLE ai_run_tools (
    run_id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    revision bigint NOT NULL,
    config jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
CREATE TABLE ai_tool_versions (
    run_id uuid NOT NULL,
    project_id uuid NOT NULL,
    revision bigint NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    config jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(run_id,revision),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
-- A deployment-wide scheduling index, like jobs; no prompts or credentials.
CREATE TABLE ai_tool_schedules (
    run_id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    next_poll_at timestamptz NOT NULL DEFAULT now(),
    state jsonb NOT NULL DEFAULT '{}',
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE
);
CREATE INDEX ai_tools_due ON ai_tool_schedules(next_poll_at) WHERE enabled;
ALTER TABLE ai_calls ADD CONSTRAINT ai_calls_project_identity UNIQUE(project_id,id);
CREATE TABLE ai_call_checkpoints (
    project_id uuid NOT NULL,
    call_id uuid NOT NULL,
    run_id uuid NOT NULL,
    checkpoint_id uuid NOT NULL,
    PRIMARY KEY(call_id,checkpoint_id),
    FOREIGN KEY(project_id,call_id) REFERENCES ai_calls(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id,checkpoint_id) REFERENCES checkpoints(project_id,run_id,id)
);
ALTER TABLE research_plans ADD COLUMN ai_call_id uuid;
ALTER TABLE research_plans ADD COLUMN derived_from uuid;
ALTER TABLE research_plans ADD CONSTRAINT research_plan_derivation
    FOREIGN KEY(project_id,run_id,derived_from) REFERENCES research_plans(project_id,run_id,id);
ALTER TABLE research_plans ADD CONSTRAINT research_plan_ai_call
    FOREIGN KEY(project_id,ai_call_id) REFERENCES ai_calls(project_id,id);
DO $$ DECLARE tab text; BEGIN
    FOREACH tab IN ARRAY ARRAY['ai_run_tools','ai_tool_versions','ai_call_checkpoints'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',tab);
    END LOOP;
END $$;
INSERT INTO schema_version(version) VALUES(19);
