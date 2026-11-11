SET search_path TO tm2,pg_catalog;

CREATE TABLE probe_calibrations (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    run_id uuid NOT NULL,
    checkpoint_id uuid NOT NULL,
    source_hash text NOT NULL,
    protocol jsonb NOT NULL,
    sensor_config jsonb NOT NULL,
    sensor_seed bigint NOT NULL,
    job_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id), UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,checkpoint_id) REFERENCES checkpoints(project_id,id),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id)
);
CREATE INDEX probe_calibrations_run ON probe_calibrations(project_id,run_id,created_at DESC,id DESC);
ALTER TABLE probe_calibrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE probe_calibrations FORCE ROW LEVEL SECURITY;
CREATE POLICY project_scope ON probe_calibrations
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE FUNCTION preserve_probe_calibration() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'probe source and protocol are immutable' USING ERRCODE='55000';
END $$;
CREATE TRIGGER immutable_probe BEFORE UPDATE OR DELETE ON probe_calibrations
    FOR EACH ROW EXECUTE FUNCTION preserve_probe_calibration();

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v48;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind='probe_calibration' THEN RETURN ARRAY['worker.core','worker.probe_calibration_v1']; END IF;
    RETURN required_job_features_v48(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(49);
