SET search_path TO tm2,pg_catalog;
ALTER TABLE jobs ADD COLUMN required_features text[] NOT NULL DEFAULT '{}';

CREATE FUNCTION required_job_features(task_kind text, task_run uuid, task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE spec jsonb; features text[]; scope text;
BEGIN
    IF task_kind='ai' THEN RETURN ARRAY['worker.ai']; END IF;
    IF task_kind='notification' THEN RETURN ARRAY['worker.notifications']; END IF;
    features := ARRAY['worker.core'];
    IF task_kind='study' THEN spec := task_params->'protocol'->'base';
    ELSIF task_kind IN ('run','research_plan') THEN SELECT runs.spec INTO spec FROM runs WHERE id=task_run;
    END IF;
    IF spec->>'environment'='mujoco' THEN features := array_append(features,'worker.mujoco'); END IF;
    IF coalesce((spec#>>'{source_policies,background_enabled}')::boolean,true) THEN
        FOREACH scope IN ARRAY ARRAY['host','process','runtime'] LOOP
            IF spec#>ARRAY[scope||'_telemetry','enabled']='true'::jsonb
               AND coalesce((spec#>>ARRAY['source_policies',scope||'_enabled'])::boolean,true) THEN
                features := array_append(features,'worker.telemetry_'||scope);
            END IF;
        END LOOP;
    END IF;
    RETURN features;
END $$;

CREATE FUNCTION set_job_features() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' OR NEW.status='pending' THEN
        NEW.required_features := required_job_features(NEW.kind,NEW.run_id,NEW.params);
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER job_features BEFORE INSERT OR UPDATE OF kind,run_id,params ON jobs
FOR EACH ROW EXECUTE FUNCTION set_job_features();

CREATE FUNCTION refresh_run_job_features() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE jobs SET required_features=required_job_features(kind,run_id,params)
    WHERE run_id=NEW.id AND status='pending';
    RETURN NEW;
END $$;
CREATE TRIGGER run_job_features AFTER UPDATE OF spec ON runs
FOR EACH ROW WHEN (OLD.spec IS DISTINCT FROM NEW.spec) EXECUTE FUNCTION refresh_run_job_features();

-- Only small queued-job metadata is upgraded; closed historical evidence is not guessed.
DO $$ DECLARE project uuid;
BEGIN
    FOR project IN SELECT DISTINCT project_id FROM jobs WHERE status IN ('pending','leased') LOOP
        PERFORM set_config('tm.project_id',project::text,true);
        UPDATE jobs SET required_features=required_job_features(kind,run_id,params)
        WHERE project_id=project AND status IN ('pending','leased');
    END LOOP;
    PERFORM set_config('tm.project_id','',true);
END $$;

CREATE TABLE job_assignments (
    project_id uuid NOT NULL,
    job_id uuid NOT NULL,
    generation bigint NOT NULL,
    worker_id text NOT NULL REFERENCES workers(id),
    required_features text[] NOT NULL,
    capabilities jsonb NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(job_id,generation),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id) ON DELETE CASCADE
);
ALTER TABLE job_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_assignments FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON job_assignments
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE INDEX jobs_project_recent ON jobs(project_id,created_at DESC,id DESC);
INSERT INTO schema_version(version) VALUES(24);
