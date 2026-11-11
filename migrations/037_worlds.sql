SET search_path TO tm2,pg_catalog;

CREATE TABLE world_documents (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    title text NOT NULL,
    revision bigint NOT NULL CHECK(revision>=0),
    archived boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id)
);
CREATE TABLE world_versions (
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision>=1),
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    protocol jsonb NOT NULL,
    protocol_hash text NOT NULL,
    physical_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(document_id,revision),
    UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,document_id) REFERENCES world_documents(project_id,id)
);
CREATE INDEX worlds_recent ON world_documents(project_id,updated_at DESC,id DESC);
CREATE INDEX worlds_protocol_hash ON world_versions(project_id,protocol_hash);
CREATE FUNCTION preserve_world_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'world versions are immutable; save a new revision' USING ERRCODE='55000';
END $$;
CREATE TRIGGER immutable_world_version BEFORE UPDATE OR DELETE ON world_versions
FOR EACH ROW EXECUTE FUNCTION preserve_world_version();
DO $$ DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['world_documents','world_versions'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
        EXECUTE format('CREATE POLICY project_scope ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',t);
    END LOOP;
END $$;

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v36;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; spec jsonb;
BEGIN
    features := required_job_features_v36(task_kind,task_run,task_params);
    IF task_kind IN ('run','research_plan') THEN
        SELECT runs.spec INTO spec FROM runs WHERE id=task_run;
    ELSIF task_kind='study' THEN
        spec := task_params->'protocol'->'base';
    END IF;
    IF spec->>'environment'='world' THEN
        features := array_append(features,'worker.world_v1');
        IF EXISTS(SELECT 1 FROM jsonb_array_elements(spec->'world_protocol'->'sensors') s WHERE s->>'kind'='camera_rgb') THEN
            features := array_append(features,'worker.world_rgb_v1');
        END IF;
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(37);
