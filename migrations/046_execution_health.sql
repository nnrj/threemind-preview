SET search_path TO tm2,pg_catalog;
ALTER TABLE workers ADD COLUMN health jsonb NOT NULL DEFAULT '{}';
ALTER TABLE workers ADD COLUMN health_received_at timestamptz;
-- Unknown historical transition times remain NULL, never reconstructed.
ALTER TABLE jobs ADD COLUMN status_changed_at timestamptz;
ALTER TABLE jobs ALTER COLUMN status_changed_at SET DEFAULT clock_timestamp();
CREATE FUNCTION timestamp_job_status() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.status_changed_at:=clock_timestamp(); RETURN NEW; END $$;
CREATE TRIGGER timestamp_job_status BEFORE UPDATE OF status ON jobs
    FOR EACH ROW EXECUTE FUNCTION timestamp_job_status();
CREATE TABLE execution_health_monitors (
    project_id uuid PRIMARY KEY REFERENCES projects(id),
    policy_revision bigint NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    next_poll_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    state jsonb NOT NULL DEFAULT '{}',
    snapshot jsonb NOT NULL DEFAULT '{}',
    error text,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE execution_health_monitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_health_monitors FORCE ROW LEVEL SECURITY;
CREATE POLICY health_project ON execution_health_monitors
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE POLICY health_scheduler ON execution_health_monitors
    USING(current_setting('tm.ai_admin',true)='true')
    WITH CHECK(current_setting('tm.ai_admin',true)='true');
CREATE INDEX execution_health_due ON execution_health_monitors(next_poll_at) WHERE enabled;
DROP TRIGGER notification_job_finished ON jobs;
CREATE TRIGGER notification_job_finished AFTER UPDATE OF status ON jobs FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status AND
        ((NEW.status='failed' AND NEW.kind NOT IN ('notification','run','ai','ecology_observe'))
         OR (NEW.status='done' AND NEW.kind IN ('export','data_export','analysis'))))
    EXECUTE FUNCTION notify_job_finished();
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v45;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[];
BEGIN
    features:=required_job_features_v45(task_kind,task_run,task_params);
    IF task_kind='notification' THEN features:=array_append(features,'worker.execution_health_v1'); END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(46);
