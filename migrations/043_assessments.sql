SET search_path TO tm2,pg_catalog;

CREATE TABLE assessment_batches (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    name text NOT NULL,
    objective text NOT NULL,
    source_version_id uuid NOT NULL,
    protocol jsonb NOT NULL,
    protocol_hash text NOT NULL,
    revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
    control_state text NOT NULL DEFAULT 'active' CHECK(control_state IN ('active','paused','cancelled')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id), UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,source_version_id) REFERENCES innate_versions(project_id,id)
);
CREATE TABLE assessment_members (
    project_id uuid NOT NULL,
    batch_id uuid NOT NULL,
    block_index integer NOT NULL CHECK(block_index BETWEEN 0 AND 31),
    environment_seed bigint NOT NULL CHECK(environment_seed BETWEEN 0 AND 4294967295),
    run_id uuid NOT NULL UNIQUE,
    PRIMARY KEY(batch_id,block_index),
    UNIQUE(batch_id,environment_seed),
    FOREIGN KEY(project_id,batch_id) REFERENCES assessment_batches(project_id,id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id)
);
CREATE TABLE assessment_actions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    batch_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    action text NOT NULL CHECK(action IN ('pause','resume','retry','cancel')),
    revision bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,operation_id), UNIQUE(batch_id,revision),
    FOREIGN KEY(project_id,batch_id) REFERENCES assessment_batches(project_id,id)
);
CREATE INDEX assessment_recent ON assessment_batches(project_id,created_at DESC,id DESC);
CREATE FUNCTION preserve_assessment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='UPDATE' AND TG_TABLE_NAME='assessment_batches' AND
       (to_jsonb(NEW)-ARRAY['revision','control_state']) IS NOT DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['revision','control_state']) THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'assessment protocol, membership and control evidence are immutable' USING ERRCODE='55000';
END $$;
DO $$ DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['assessment_batches','assessment_members','assessment_actions'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY project_scope ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',relation);
        EXECUTE format('CREATE TRIGGER immutable_assessment BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_assessment()',relation);
    END LOOP;
END $$;
ALTER TABLE report_source_requests DROP CONSTRAINT report_source_requests_kind_check;
ALTER TABLE report_source_requests ADD CHECK(kind IN ('trajectory','nodes','edges','analysis','events','evolution','ecology_trajectory','ecology_members','assessment'));
ALTER TABLE report_source_requests ADD COLUMN assessment_id uuid;
ALTER TABLE report_source_requests ADD FOREIGN KEY(project_id,assessment_id) REFERENCES assessment_batches(project_id,id);
ALTER TABLE report_source_requests ADD CHECK((kind='assessment')=(assessment_id IS NOT NULL));
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v42;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[];
BEGIN
    features := required_job_features_v42(task_kind,task_run,task_params);
    IF (task_kind='run' AND EXISTS(SELECT 1 FROM assessment_members WHERE run_id=task_run))
       OR (task_kind='report_source' AND task_params->>'source_kind'='assessment')
       OR (task_kind IN ('ai','report_export') AND task_params->>'assessment_evidence'='true') THEN
        features := array_append(features,'worker.assessment_v1');
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(43);
