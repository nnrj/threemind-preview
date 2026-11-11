SET search_path TO tm2,pg_catalog;

CREATE TABLE research_document_exports (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    document_id uuid NOT NULL,
    revision bigint NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    job_id uuid NOT NULL,
    options jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,document_id,revision)
        REFERENCES research_document_versions(project_id,document_id,revision),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id)
);
ALTER TABLE research_document_exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_document_exports FORCE ROW LEVEL SECURITY;
CREATE POLICY project_scope ON research_document_exports
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE TRIGGER immutable_export BEFORE UPDATE OR DELETE ON research_document_exports
    FOR EACH ROW EXECUTE FUNCTION preserve_research_evidence();
CREATE INDEX research_document_exports_recent ON research_document_exports(project_id,document_id,created_at DESC);

-- E2a workers know captures, but cannot execute the new document renderers.
CREATE OR REPLACE FUNCTION required_job_features(task_kind text, task_run uuid, task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind='report_export' THEN RETURN ARRAY['worker.report_export_v1']; END IF;
    IF task_kind='report_source' THEN RETURN ARRAY['worker.research_documents']; END IF;
    RETURN required_job_features_v24(task_kind,task_run,task_params);
END $$;
UPDATE jobs SET required_features=required_job_features(kind,run_id,params)
    WHERE kind='report_export' AND status='pending';
INSERT INTO schema_version(version) VALUES(27);
