SET search_path TO tm2,pg_catalog;

-- References pin committed state; no duplicate graph blob or mutable model file.
CREATE TABLE innate_versions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    name text NOT NULL,
    selection_note text NOT NULL,
    run_id uuid NOT NULL,
    checkpoint_id uuid NOT NULL,
    state_hash text NOT NULL,
    source_revision bigint NOT NULL,
    source_time_us numeric(39,0) NOT NULL,
    protocol jsonb NOT NULL,
    protocol_hash text NOT NULL,
    birth_rule text NOT NULL CHECK(birth_rule='threemind.birth/1'),
    parent_version_id uuid,
    generation integer NOT NULL CHECK(generation>=0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id), UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,checkpoint_id) REFERENCES checkpoints(project_id,id),
    FOREIGN KEY(project_id,parent_version_id) REFERENCES innate_versions(project_id,id),
    CHECK((parent_version_id IS NULL AND generation=0) OR (parent_version_id IS NOT NULL AND generation>0))
);
CREATE TABLE development_sessions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    name text NOT NULL,
    objective text NOT NULL,
    run_id uuid NOT NULL UNIQUE,
    source_version_id uuid,
    protocol jsonb NOT NULL,
    protocol_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id), UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,source_version_id) REFERENCES innate_versions(project_id,id)
);
CREATE INDEX development_recent ON development_sessions(project_id,created_at DESC,id DESC);
CREATE INDEX innate_recent ON innate_versions(project_id,created_at DESC,id DESC);
CREATE INDEX innate_source ON innate_versions(run_id,checkpoint_id);
CREATE INDEX innate_parent ON innate_versions(parent_version_id) WHERE parent_version_id IS NOT NULL;

CREATE FUNCTION preserve_development_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'development registrations are immutable; register a new version' USING ERRCODE='55000';
END $$;
DO $$ DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['development_sessions','innate_versions'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY project_scope ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',table_name);
        EXECUTE format('CREATE TRIGGER immutable_development BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_development_record()',table_name);
    END LOOP;
END $$;

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v30;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[];
BEGIN
    features := required_job_features_v30(task_kind,task_run,task_params);
    IF (task_kind='run' AND EXISTS(SELECT 1 FROM development_sessions WHERE run_id=task_run))
       OR (task_kind='export' AND task_params ? 'innate_version_id') THEN
        features := array_append(features,'worker.development_v1');
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(31);
