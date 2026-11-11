SET search_path TO tm2,pg_catalog;

-- A scientific index, never a synthetic runtime or a replacement for originals.
CREATE TABLE research_experiments (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    source_key text NOT NULL, original_id text, title text NOT NULL,
    classification text NOT NULL CHECK(classification IN ('formal','proposal','calibration','development')),
    execution_status text NOT NULL CHECK(execution_status IN ('planned','running','completed','failed','interrupted','cancelled','unknown')),
    coverage text NOT NULL DEFAULT 'indexed' CHECK(coverage IN ('indexed','partial','verified')),
    experiment_date date, executor text NOT NULL, kernels jsonb NOT NULL,
    spec jsonb NOT NULL, content_hash text NOT NULL,
    created_by uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), UNIQUE(project_id,source_key)
);
CREATE INDEX research_experiments_recent ON research_experiments(project_id,experiment_date DESC,id);
CREATE TABLE research_record_requests (
    project_id uuid NOT NULL REFERENCES projects(id), actor_id uuid NOT NULL REFERENCES users(id),
    request_id uuid NOT NULL, action text NOT NULL, fingerprint text NOT NULL,
    result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,actor_id,request_id)
);
CREATE TABLE research_record_entries (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, experiment_id uuid NOT NULL,
    kind text NOT NULL CHECK(kind IN ('subject','condition','stage','process','result','correction','gap')),
    original_key text NOT NULL, content jsonb NOT NULL, content_hash text NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id), recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), UNIQUE(experiment_id,kind,original_key),
    FOREIGN KEY(project_id,experiment_id) REFERENCES research_experiments(project_id,id)
);
CREATE TABLE research_evidence_grants (
    project_id uuid NOT NULL REFERENCES projects(id), resource_id text NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,resource_id)
);
CREATE TABLE research_record_evidence (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, experiment_id uuid NOT NULL,
    logical_id text NOT NULL, role text NOT NULL, label text NOT NULL, format text NOT NULL,
    byte_count bigint CHECK(byte_count>=0), sha256 text, locator jsonb NOT NULL,
    stage_key text, dependencies jsonb NOT NULL DEFAULT '[]',
    private_actor_id uuid REFERENCES users(id),
    document_id uuid, document_revision bigint, note_id uuid, note_revision bigint,
    artifact_id uuid, run_id uuid, checkpoint_id uuid, data_bundle_id uuid,
    content_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), UNIQUE(experiment_id,logical_id),
    FOREIGN KEY(project_id,experiment_id) REFERENCES research_experiments(project_id,id),
    FOREIGN KEY(project_id,document_id,document_revision) REFERENCES research_document_versions(project_id,document_id,revision),
    FOREIGN KEY(project_id,private_actor_id,note_id,note_revision) REFERENCES note_versions(project_id,owner_id,note_id,revision),
    FOREIGN KEY(project_id,artifact_id) REFERENCES artifacts(project_id,id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,checkpoint_id) REFERENCES checkpoints(project_id,id),
    FOREIGN KEY(project_id,data_bundle_id) REFERENCES data_bundles(project_id,id)
);
CREATE INDEX research_record_evidence_experiment ON research_record_evidence(experiment_id,role,id);
-- Presence only, never note identities or text. Needed to reject an export
-- that would silently omit another author's invisible personal evidence.
CREATE TABLE research_record_private_counts (
    project_id uuid NOT NULL, experiment_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
    PRIMARY KEY(experiment_id,actor_id),
    FOREIGN KEY(project_id,experiment_id) REFERENCES research_experiments(project_id,id)
);
CREATE FUNCTION register_record_private_author() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    IF NEW.private_actor_id IS NOT NULL THEN
        INSERT INTO research_record_private_counts VALUES(NEW.project_id,NEW.experiment_id,NEW.private_actor_id) ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER record_private_author AFTER INSERT ON research_record_evidence
    FOR EACH ROW EXECUTE FUNCTION register_record_private_author();
CREATE TABLE research_backfill_batches (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id), plan jsonb NOT NULL, plan_hash text NOT NULL,
    state text NOT NULL DEFAULT 'preview' CHECK(state IN ('preview','applied')),
    result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), UNIQUE(project_id,actor_id,plan_hash)
);
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['research_experiments','research_record_requests','research_record_entries',
        'research_evidence_grants','research_record_evidence','research_record_private_counts','research_backfill_batches'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',relation);
    END LOOP;
END $$;
-- Only the index supports a cross-project view, and only for actual members.
CREATE POLICY research_index_member_read ON research_experiments FOR SELECT USING(
    EXISTS(SELECT 1 FROM members m JOIN users u ON u.id=m.user_id WHERE m.project_id=research_experiments.project_id
        AND m.user_id::text=current_setting('tm.record_user_id',true) AND u.enabled)
);
DROP POLICY project_boundary ON research_record_evidence;
CREATE POLICY project_boundary ON research_record_evidence USING(project_id::text=current_setting('tm.project_id',true)
    AND (private_actor_id IS NULL OR private_actor_id::text=current_setting('tm.note_user_id',true)))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true)
    AND (private_actor_id IS NULL OR private_actor_id::text=current_setting('tm.note_user_id',true)));
CREATE TRIGGER immutable_record_entry BEFORE UPDATE OR DELETE ON research_record_entries
    FOR EACH ROW EXECUTE FUNCTION preserve_research_evidence();
CREATE TRIGGER immutable_record_evidence BEFORE UPDATE OR DELETE ON research_record_evidence
    FOR EACH ROW EXECUTE FUNCTION preserve_research_evidence();
CREATE TRIGGER immutable_record_receipt BEFORE UPDATE OR DELETE ON research_record_requests
    FOR EACH ROW EXECUTE FUNCTION preserve_research_evidence();
INSERT INTO schema_version(version) VALUES(62);
