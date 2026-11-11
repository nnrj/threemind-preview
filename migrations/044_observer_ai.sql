SET search_path TO tm2,pg_catalog;
CREATE TABLE ecology_ai_revisions (
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision>0),
    configuration jsonb NOT NULL,
    configuration_hash text NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(campaign_id,revision), UNIQUE(project_id,campaign_id,revision),
    FOREIGN KEY(project_id,campaign_id) REFERENCES ecology_campaigns(project_id,id)
);
CREATE TABLE ecology_ai_schedules (
    campaign_id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    revision bigint NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    next_poll_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    state jsonb NOT NULL DEFAULT '{}',
    FOREIGN KEY(project_id,campaign_id,revision) REFERENCES ecology_ai_revisions(project_id,campaign_id,revision)
);
CREATE TABLE ecology_ai_sources (
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    configuration_revision bigint NOT NULL,
    call_id uuid PRIMARY KEY REFERENCES ai_calls(id),
    checkpoint_id uuid NOT NULL,
    first_revision bigint NOT NULL CHECK(first_revision>0),
    FOREIGN KEY(project_id,campaign_id,configuration_revision) REFERENCES ecology_ai_revisions(project_id,campaign_id,revision),
    FOREIGN KEY(project_id,campaign_id,checkpoint_id) REFERENCES ecology_checkpoints(project_id,campaign_id,id)
);
CREATE INDEX ecology_ai_calls ON ecology_ai_sources(campaign_id,configuration_revision);
CREATE INDEX ecology_ai_poll ON ecology_ai_schedules(next_poll_at) WHERE enabled;
DO $$ DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['ecology_ai_revisions','ecology_ai_schedules','ecology_ai_sources'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY project_scope ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['ecology_ai_revisions','ecology_ai_sources'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_ecology_ai BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_ecology_record()',relation);
    END LOOP;
END $$;
-- Only the explicit scheduler/admin context can discover due subscriptions.
CREATE POLICY scheduler_scope ON ecology_ai_schedules
    USING(current_setting('tm.ai_admin',true)='true')
    WITH CHECK(current_setting('tm.ai_admin',true)='true');
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v43;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind='ai' AND task_params->>'purpose'='ecology_observation' THEN
        RETURN ARRAY['worker.ai','worker.ecology_ai_v1'];
    END IF;
    RETURN required_job_features_v43(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(44);
