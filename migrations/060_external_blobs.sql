SET search_path TO tm2,pg_catalog;
CREATE TABLE stored_blobs (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    bytes bigint NOT NULL CHECK(bytes>=0), sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
    locator jsonb NOT NULL, version_id text, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), CHECK(jsonb_typeof(locator)='object'
        AND locator ?& ARRAY['kind','target_id','config_revision','host_id','key']
        AND jsonb_typeof(locator->'kind')='string' AND locator->>'kind' IN ('filesystem','s3')
        AND jsonb_typeof(locator->'target_id')='string' AND length(locator->>'target_id') BETWEEN 1 AND 160
        AND jsonb_typeof(locator->'host_id')='string' AND length(locator->>'host_id') BETWEEN 1 AND 160
        AND jsonb_typeof(locator->'key')='string' AND length(locator->>'key') BETWEEN 1 AND 1024
        AND jsonb_typeof(locator->'config_revision')='number' AND (locator->>'config_revision')::bigint>0)
);
ALTER TABLE stored_blobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE stored_blobs FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON stored_blobs USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE FUNCTION preserve_blob() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'registered external blob locations and bytes are immutable' USING ERRCODE='55000'; END $$;
CREATE TRIGGER preserve_stored_blob BEFORE UPDATE ON stored_blobs FOR EACH ROW EXECUTE FUNCTION preserve_blob();
CREATE TABLE blob_backup_leases (
    backup_id uuid NOT NULL, blob_id uuid NOT NULL REFERENCES stored_blobs(id),
    project_id uuid NOT NULL REFERENCES projects(id), created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(backup_id,blob_id)
);
ALTER TABLE blob_backup_leases ENABLE ROW LEVEL SECURITY;
ALTER TABLE blob_backup_leases FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON blob_backup_leases USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE TABLE blob_tombstones(id uuid PRIMARY KEY,project_id uuid NOT NULL REFERENCES projects(id),
    plan jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE blob_tombstones ENABLE ROW LEVEL SECURITY;
ALTER TABLE blob_tombstones FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON blob_tombstones USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
ALTER TABLE artifacts ADD COLUMN blob_id uuid;
ALTER TABLE artifacts ADD FOREIGN KEY(project_id,blob_id) REFERENCES stored_blobs(project_id,id);
ALTER TABLE media_assets ADD COLUMN blob_id uuid;
ALTER TABLE media_assets ADD FOREIGN KEY(project_id,blob_id) REFERENCES stored_blobs(project_id,id);
ALTER TABLE note_assets ADD COLUMN blob_id uuid;
ALTER TABLE note_assets ALTER COLUMN content DROP NOT NULL;
ALTER TABLE note_assets ADD FOREIGN KEY(project_id,blob_id) REFERENCES stored_blobs(project_id,id);
ALTER TABLE note_assets ADD CHECK((content IS NULL)=(blob_id IS NOT NULL));
ALTER TABLE media_uploads ADD COLUMN storage_policy jsonb NOT NULL DEFAULT '{"kind":"db","category":"media-original","policy_revision":0}';
ALTER TABLE capture_sessions ADD COLUMN storage_policy jsonb NOT NULL DEFAULT '{"kind":"db","category":"media-original","policy_revision":0}';
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v59;
CREATE FUNCTION required_job_features(task_kind text, task_run uuid, task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; p jsonb; item jsonb;
BEGIN
    features:=required_job_features_v59(task_kind,task_run,task_params);
    p:=task_params->'storage_policy';
    IF p->>'kind' IN ('filesystem','s3') THEN
        features:=array_append(features,'storage.target:'||(p->>'target_id')||':'||(p->>'config_revision')||'@'||(p->>'host_id'));
    END IF;
    FOR item IN SELECT value FROM jsonb_array_elements(COALESCE(task_params->'source_targets','[]'::jsonb)) LOOP
        IF item->>'kind' IN ('filesystem','s3') THEN
            features:=array_append(features,'storage.target:'||(item->>'target_id')||':'||(item->>'config_revision')||'@'||(item->>'host_id'));
        END IF;
    END LOOP;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(60);
