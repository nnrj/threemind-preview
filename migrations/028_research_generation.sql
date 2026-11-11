SET search_path TO tm2,pg_catalog;

CREATE TABLE research_generations (
    project_id uuid NOT NULL REFERENCES projects(id),
    call_id uuid PRIMARY KEY,
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    request jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,call_id),
    UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,call_id) REFERENCES ai_calls(project_id,id)
);
CREATE TABLE research_generation_sources (
    project_id uuid NOT NULL,
    call_id uuid NOT NULL,
    source_id uuid NOT NULL,
    PRIMARY KEY(call_id,source_id),
    FOREIGN KEY(project_id,call_id) REFERENCES research_generations(project_id,call_id),
    FOREIGN KEY(project_id,source_id) REFERENCES report_sources(project_id,id)
);
CREATE TABLE research_generation_records (
    project_id uuid NOT NULL,
    call_id uuid NOT NULL,
    record_id uuid NOT NULL,
    revision bigint NOT NULL,
    PRIMARY KEY(call_id,record_id,revision),
    FOREIGN KEY(project_id,call_id) REFERENCES research_generations(project_id,call_id),
    FOREIGN KEY(project_id,record_id,revision) REFERENCES research_document_versions(project_id,document_id,revision)
);
DO $$ DECLARE tab text; BEGIN
    FOREACH tab IN ARRAY ARRAY['research_generations','research_generation_sources','research_generation_records'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY project_scope ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',tab);
        EXECUTE format('CREATE TRIGGER immutable_generation BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_research_evidence()',tab);
    END LOOP;
END $$;
CREATE INDEX research_generation_source_refs ON research_generation_sources(project_id,source_id);

CREATE OR REPLACE FUNCTION required_job_features(task_kind text, task_run uuid, task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind='ai' AND task_params->>'purpose' IN ('record','report') THEN
        RETURN ARRAY['worker.ai','worker.research_ai_v1'];
    END IF;
    IF task_kind='report_export' THEN RETURN ARRAY['worker.report_export_v1']; END IF;
    IF task_kind='report_source' THEN RETURN ARRAY['worker.research_documents']; END IF;
    RETURN required_job_features_v24(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(28);
