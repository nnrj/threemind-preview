SET search_path TO tm2,pg_catalog;
CREATE TABLE bundle_uploads (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id), request_id uuid NOT NULL,
    name text NOT NULL, bytes bigint NOT NULL CHECK(bytes > 0 AND bytes <= 8589934592),
    sha256 text CHECK(sha256 IS NULL OR length(sha256)=64),
    status text NOT NULL DEFAULT 'receiving' CHECK(status IN ('receiving','queued','ready','failed')),
    job_id uuid REFERENCES jobs(id), created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), UNIQUE(project_id,actor_id,request_id)
);
CREATE TABLE bundle_upload_chunks (
    project_id uuid NOT NULL, upload_id uuid NOT NULL, ordinal integer NOT NULL CHECK(ordinal>=0),
    sha256 text NOT NULL, body bytea NOT NULL CHECK(octet_length(body) BETWEEN 1 AND 4194304),
    PRIMARY KEY(upload_id,ordinal),
    FOREIGN KEY(project_id,upload_id) REFERENCES bundle_uploads(project_id,id) ON DELETE CASCADE
);
CREATE TABLE experiment_bundles (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id), name text NOT NULL,
    job_id uuid NOT NULL REFERENCES jobs(id), artifact_id uuid, upload_id uuid,
    sha256 text NOT NULL, bytes bigint NOT NULL, manifest jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), UNIQUE(job_id),
    CHECK((artifact_id IS NULL) <> (upload_id IS NULL)),
    FOREIGN KEY(project_id,artifact_id) REFERENCES artifacts(project_id,id),
    FOREIGN KEY(project_id,upload_id) REFERENCES bundle_uploads(project_id,id)
);
CREATE TABLE bundle_resumes (
    project_id uuid NOT NULL, bundle_id uuid NOT NULL, run_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id), request_id uuid NOT NULL,
    fingerprint text NOT NULL, conditions jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,actor_id,request_id), UNIQUE(run_id),
    FOREIGN KEY(project_id,bundle_id) REFERENCES experiment_bundles(project_id,id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id)
);
DO $$ DECLARE tab text; BEGIN
    FOREACH tab IN ARRAY ARRAY['bundle_uploads','bundle_upload_chunks','experiment_bundles','bundle_resumes'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',tab);
    END LOOP;
END $$;
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v52;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$ BEGIN
    IF task_kind IN ('bundle_export','bundle_import','bundle_resume') THEN RETURN ARRAY['worker.experiment_bundle_v1']; END IF;
    RETURN required_job_features_v52(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(53);
