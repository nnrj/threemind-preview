SET search_path TO tm2,pg_catalog;

CREATE TABLE report_source_requests (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    kind text NOT NULL CHECK(kind IN ('trajectory','nodes','edges','analysis')),
    run_id uuid,
    checkpoint_id uuid,
    analysis_artifact_id uuid,
    job_id uuid NOT NULL,
    selection jsonb NOT NULL,
    provenance jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id),
    UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,checkpoint_id) REFERENCES checkpoints(project_id,id),
    FOREIGN KEY(project_id,analysis_artifact_id) REFERENCES artifacts(project_id,id),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id)
);
CREATE TABLE report_sources (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    manifest jsonb NOT NULL,
    content_hash text NOT NULL,
    row_count bigint NOT NULL CHECK(row_count>=0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id),
    FOREIGN KEY(project_id,id) REFERENCES report_source_requests(project_id,id) ON DELETE CASCADE
);
CREATE TABLE report_source_rows (
    project_id uuid NOT NULL,
    source_id uuid NOT NULL,
    ordinal bigint NOT NULL CHECK(ordinal>=0),
    time_us numeric(39,0),
    label text NOT NULL,
    quality text NOT NULL,
    values jsonb NOT NULL,
    provenance jsonb NOT NULL,
    PRIMARY KEY(source_id,ordinal),
    FOREIGN KEY(project_id,source_id) REFERENCES report_sources(project_id,id)
        ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE research_documents (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    kind text NOT NULL CHECK(kind IN ('record','report')),
    title text NOT NULL,
    revision bigint NOT NULL CHECK(revision>=1),
    archived_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id)
);
CREATE TABLE research_document_versions (
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision>=1),
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    spec jsonb NOT NULL,
    review text NOT NULL CHECK(review IN ('draft','reviewed')),
    ai_call_id uuid,
    content_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(document_id,revision),
    UNIQUE(project_id,document_id,revision),
    UNIQUE(document_id,operation_id),
    FOREIGN KEY(project_id,document_id) REFERENCES research_documents(project_id,id),
    FOREIGN KEY(project_id,ai_call_id) REFERENCES ai_calls(project_id,id)
);
CREATE TABLE research_document_sources (
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision bigint NOT NULL,
    source_id uuid NOT NULL,
    PRIMARY KEY(document_id,revision,source_id),
    FOREIGN KEY(project_id,document_id,revision) REFERENCES research_document_versions(project_id,document_id,revision),
    FOREIGN KEY(project_id,source_id) REFERENCES report_sources(project_id,id)
);
CREATE TABLE research_document_refs (
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision bigint NOT NULL,
    record_id uuid NOT NULL,
    record_revision bigint NOT NULL,
    block_id text NOT NULL,
    PRIMARY KEY(document_id,revision,record_id,record_revision,block_id),
    FOREIGN KEY(project_id,document_id,revision) REFERENCES research_document_versions(project_id,document_id,revision),
    FOREIGN KEY(project_id,record_id,record_revision) REFERENCES research_document_versions(project_id,document_id,revision)
);
DO $$ DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['report_source_requests','report_sources','report_source_rows',
        'research_documents','research_document_versions','research_document_sources','research_document_refs'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',relation);
    END LOOP;
END $$;
CREATE FUNCTION preserve_research_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'captured research evidence and document revisions are immutable' USING ERRCODE='55000';
END $$;
CREATE FUNCTION reject_completed_source_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM report_sources WHERE id=NEW.source_id) THEN
        RAISE EXCEPTION 'cannot append rows to a completed evidence capture' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER completed_source BEFORE INSERT ON report_source_rows
    FOR EACH ROW EXECUTE FUNCTION reject_completed_source_insert();
CREATE FUNCTION reject_partial_source_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM report_sources WHERE id=OLD.source_id) THEN
        RAISE EXCEPTION 'delete the unused capture as a whole, not its evidence rows' USING ERRCODE='55000';
    END IF;
    RETURN OLD;
END $$;
CREATE TRIGGER whole_source_delete BEFORE DELETE ON report_source_rows
    FOR EACH ROW EXECUTE FUNCTION reject_partial_source_delete();
DO $$ DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['report_source_requests','report_sources','report_source_rows'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_evidence BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_research_evidence()',relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['research_document_versions','research_document_sources','research_document_refs'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_document BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_research_evidence()',relation);
    END LOOP;
END $$;
CREATE INDEX report_source_requests_recent ON report_source_requests(project_id,created_at DESC,id DESC);
CREATE INDEX research_documents_recent ON research_documents(project_id,kind,updated_at DESC,id DESC);

-- Old workers must not claim jobs whose evidence contract they do not implement.
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v24;
CREATE FUNCTION required_job_features(task_kind text, task_run uuid, task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind IN ('report_source','report_export') THEN RETURN ARRAY['worker.research_documents']; END IF;
    RETURN required_job_features_v24(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(26);
