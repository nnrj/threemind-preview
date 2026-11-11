SET search_path TO tm2,pg_catalog;
-- Scientific original locators remain immutable. Physical placements have an
-- append-only history and a separately fenced current head.
CREATE TABLE blob_location_versions (
    project_id uuid NOT NULL REFERENCES projects(id), blob_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision>0), locator jsonb NOT NULL,
    version_id text, carrier_blob_id uuid NOT NULL, operation_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(blob_id,revision), UNIQUE(project_id,blob_id,revision),
    FOREIGN KEY(project_id,blob_id) REFERENCES stored_blobs(project_id,id),
    FOREIGN KEY(project_id,carrier_blob_id) REFERENCES stored_blobs(project_id,id),
    CHECK(jsonb_typeof(locator)='object' AND locator ?& ARRAY['kind','target_id','config_revision','host_id','key']
        AND locator->>'kind' IN ('filesystem','s3'))
);
CREATE TABLE blob_location_heads (
    project_id uuid NOT NULL REFERENCES projects(id), blob_id uuid PRIMARY KEY,
    revision bigint NOT NULL,
    FOREIGN KEY(project_id,blob_id,revision) REFERENCES blob_location_versions(project_id,blob_id,revision)
);
CREATE TRIGGER immutable_blob_placement BEFORE UPDATE ON blob_location_versions
    FOR EACH ROW EXECUTE FUNCTION preserve_blob();
ALTER TABLE checkpoints ADD COLUMN blob_id uuid;
ALTER TABLE checkpoints ADD FOREIGN KEY(project_id,blob_id) REFERENCES stored_blobs(project_id,id);
CREATE INDEX checkpoints_external_payload ON checkpoints(blob_id) WHERE blob_id IS NOT NULL;
-- A migration retains the original DB bytes until separately authorized cleanup.
DO $$ DECLARE constraint_name text; BEGIN
    FOR constraint_name IN SELECT conname FROM pg_constraint WHERE conrelid='note_assets'::regclass
        AND contype='c' AND pg_get_constraintdef(oid) LIKE '%blob_id%' AND pg_get_constraintdef(oid) LIKE '%content%' LOOP
        EXECUTE format('ALTER TABLE note_assets DROP CONSTRAINT %I',constraint_name);
    END LOOP;
END $$;
ALTER TABLE note_assets ADD CONSTRAINT note_payload_available CHECK(content IS NOT NULL OR blob_id IS NOT NULL);
CREATE FUNCTION preserve_note_asset_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    IF (to_jsonb(NEW)-'blob_id') IS DISTINCT FROM (to_jsonb(OLD)-'blob_id') THEN
        RAISE EXCEPTION 'saved note image identity and bytes are immutable' USING ERRCODE='55000';
    END IF;
    IF NEW.blob_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stored_blobs b WHERE b.project_id=NEW.project_id
        AND b.id=NEW.blob_id AND b.bytes=NEW.bytes AND b.sha256=NEW.sha256) THEN
        RAISE EXCEPTION 'note image placement differs from its immutable evidence' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER preserve_note_assets ON note_assets;
CREATE TRIGGER preserve_note_assets BEFORE UPDATE ON note_assets
    FOR EACH ROW EXECUTE FUNCTION preserve_note_asset_identity();
CREATE TABLE run_storage_seals (
    project_id uuid NOT NULL, run_id uuid PRIMARY KEY,
    checkpoint_id uuid NOT NULL, revision bigint NOT NULL, state_hash text NOT NULL,
    proof jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,checkpoint_id) REFERENCES checkpoints(project_id,id)
);
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['blob_location_versions','blob_location_heads','run_storage_seals'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',relation);
    END LOOP;
END $$;
INSERT INTO schema_version(version) VALUES(64);
