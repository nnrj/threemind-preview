SET search_path TO tm2,pg_catalog;
-- These are transfer plans, original imported evidence and projection mappings,
-- never a replacement for the existing scientific facts.
CREATE TABLE data_export_plans (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id), operation_id uuid NOT NULL,
    fingerprint text NOT NULL, selection jsonb NOT NULL, snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(project_id,id),
    UNIQUE(project_id,actor_id,operation_id)
);
CREATE TABLE data_plan_files (
    project_id uuid NOT NULL, plan_id uuid NOT NULL, name text NOT NULL,
    bytes bigint NOT NULL CHECK(bytes>=0), sha256 text NOT NULL,
    recipe jsonb NOT NULL, artifact_id uuid, media_sha256 text, note_asset_id uuid,
    PRIMARY KEY(plan_id,name),
    FOREIGN KEY(project_id,plan_id) REFERENCES data_export_plans(project_id,id),
    FOREIGN KEY(project_id,artifact_id) REFERENCES artifacts(project_id,id),
    FOREIGN KEY(project_id,media_sha256) REFERENCES media_assets(project_id,sha256),
    FOREIGN KEY(note_asset_id) REFERENCES note_assets(id)
);
CREATE TABLE data_plan_chunks (
    project_id uuid NOT NULL, plan_id uuid NOT NULL, name text NOT NULL,
    ordinal integer NOT NULL CHECK(ordinal>=0), body bytea NOT NULL,
    PRIMARY KEY(plan_id,name,ordinal),
    FOREIGN KEY(plan_id,name) REFERENCES data_plan_files(plan_id,name),
    CHECK(octet_length(body) BETWEEN 1 AND 4194304)
);
CREATE TABLE data_bundles (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id), name text NOT NULL,
    private boolean NOT NULL, manifest jsonb NOT NULL, bytes bigint NOT NULL CHECK(bytes>0),
    plan_id uuid, job_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id), FOREIGN KEY(project_id,plan_id) REFERENCES data_export_plans(project_id,id),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id)
);
CREATE TABLE data_bundle_volumes (
    project_id uuid NOT NULL, bundle_id uuid NOT NULL, ordinal integer NOT NULL CHECK(ordinal>=0),
    bytes bigint NOT NULL CHECK(bytes>0), sha256 text NOT NULL, blob_id uuid,
    PRIMARY KEY(bundle_id,ordinal),
    FOREIGN KEY(project_id,bundle_id) REFERENCES data_bundles(project_id,id),
    FOREIGN KEY(project_id,blob_id) REFERENCES stored_blobs(project_id,id)
);
CREATE TABLE data_bundle_chunks (
    project_id uuid NOT NULL, bundle_id uuid NOT NULL, volume integer NOT NULL, ordinal integer NOT NULL,
    body bytea NOT NULL CHECK(octet_length(body) BETWEEN 1 AND 4194304),
    PRIMARY KEY(bundle_id,volume,ordinal),
    FOREIGN KEY(bundle_id,volume) REFERENCES data_bundle_volumes(bundle_id,ordinal)
);
CREATE TABLE data_bundle_actions (
    project_id uuid NOT NULL REFERENCES projects(id), actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL, fingerprint text NOT NULL, kind text NOT NULL,
    job_id uuid, result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,actor_id,operation_id),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id)
);
CREATE TABLE data_origin_objects (
    project_id uuid NOT NULL, bundle_id uuid NOT NULL, object_id text NOT NULL,
    kind text NOT NULL, schema text NOT NULL, descriptor jsonb NOT NULL,
    PRIMARY KEY(bundle_id,object_id),
    FOREIGN KEY(project_id,bundle_id) REFERENCES data_bundles(project_id,id)
);
CREATE TABLE data_import_mappings (
    project_id uuid NOT NULL, bundle_id uuid NOT NULL, object_id text NOT NULL,
    kind text NOT NULL, old_id text NOT NULL, new_id text NOT NULL,
    original_hash text, projection_hash text, provenance jsonb NOT NULL,
    PRIMARY KEY(bundle_id,object_id),
    FOREIGN KEY(bundle_id,object_id) REFERENCES data_origin_objects(bundle_id,object_id)
);
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['data_export_plans','data_plan_files','data_plan_chunks',
        'data_bundles','data_bundle_volumes','data_bundle_chunks','data_bundle_actions',
        'data_origin_objects','data_import_mappings'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',relation);
    END LOOP;
END $$;
-- Bundle access always inherits its author's private-note boundary.
CREATE FUNCTION data_bundle_visible(bundle uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM data_bundles WHERE id=bundle AND
       (NOT private OR actor_id::text=current_setting('tm.note_user_id',true)))
$$;
DROP POLICY project_boundary ON data_bundles;
CREATE POLICY project_boundary ON data_bundles USING(project_id::text=current_setting('tm.project_id',true)
    AND (NOT private OR actor_id::text=current_setting('tm.note_user_id',true)))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true)
    AND (NOT private OR actor_id::text=current_setting('tm.note_user_id',true)));
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['data_bundle_volumes','data_bundle_chunks','data_origin_objects','data_import_mappings'] LOOP
        EXECUTE format('DROP POLICY IF EXISTS project_boundary ON %I',relation);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true) AND data_bundle_visible(bundle_id)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true) AND data_bundle_visible(bundle_id))',relation);
    END LOOP;
END $$;
-- The job below is the real import operation, never an invented old execution.
ALTER TABLE report_source_requests ADD COLUMN origin_bundle_id uuid;
ALTER TABLE report_source_requests ADD COLUMN origin_object_id text;
ALTER TABLE report_source_requests ADD FOREIGN KEY(project_id,origin_bundle_id) REFERENCES data_bundles(project_id,id);
ALTER TABLE report_source_requests ADD CHECK((origin_bundle_id IS NULL)=(origin_object_id IS NULL));
DO $$ DECLARE constraint_row record; BEGIN
    FOR constraint_row IN SELECT conname,pg_get_expr(conbin,conrelid) AS expression
        FROM pg_constraint WHERE conrelid='tm2.report_source_requests'::regclass AND contype='c'
        AND pg_get_expr(conbin,conrelid) LIKE '%IS%NULL%' AND conname NOT LIKE '%origin%' LOOP
        IF constraint_row.expression LIKE '%origin_bundle_id%' THEN CONTINUE; END IF;
        EXECUTE format('ALTER TABLE report_source_requests DROP CONSTRAINT %I',constraint_row.conname);
        EXECUTE format('ALTER TABLE report_source_requests ADD CONSTRAINT %I CHECK(origin_bundle_id IS NOT NULL OR (%s)) NOT VALID',constraint_row.conname,constraint_row.expression);
    END LOOP;
END $$;
CREATE FUNCTION validate_imported_capture() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE captured record; BEGIN
    IF NEW.origin_bundle_id IS NULL THEN RETURN NEW; END IF;
    SELECT s.row_count,s.manifest INTO captured FROM report_sources s WHERE s.id=NEW.id;
    IF captured IS NULL OR captured.row_count<>(SELECT count(*) FROM report_source_rows WHERE source_id=NEW.id)
       OR captured.manifest#>>'{import_origin,origin_bundle_id}' IS DISTINCT FROM NEW.origin_bundle_id::text
       OR captured.manifest#>>'{import_origin,origin_object_id}' IS DISTINCT FROM NEW.origin_object_id
       OR NOT EXISTS(SELECT 1 FROM data_origin_objects WHERE bundle_id=NEW.origin_bundle_id
          AND object_id=NEW.origin_object_id AND kind='source' AND schema='threemind.data.source/1')
       OR NOT EXISTS(SELECT 1 FROM jobs WHERE id=NEW.job_id AND kind='data_restore'
          AND params->>'bundle_id'=NEW.origin_bundle_id::text AND status IN ('leased','done')) THEN
        RAISE EXCEPTION 'imported capture requires complete typed fixed origin and a real import job' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER imported_capture_complete AFTER INSERT ON report_source_requests
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_imported_capture();
-- Import provenance is a projection fact, never a fabricated historical AI call.
ALTER TABLE research_document_versions ADD COLUMN import_ai_generated boolean NOT NULL DEFAULT false;
ALTER TABLE experiment_bundles ADD COLUMN private boolean NOT NULL DEFAULT false;
ALTER TABLE experiment_bundles ADD COLUMN origin_data_bundle_id uuid;
ALTER TABLE experiment_bundles ADD FOREIGN KEY(project_id,origin_data_bundle_id) REFERENCES data_bundles(project_id,id);
DROP POLICY project_boundary ON experiment_bundles;
CREATE POLICY project_boundary ON experiment_bundles USING(project_id::text=current_setting('tm.project_id',true)
    AND (NOT private OR actor_id::text=current_setting('tm.note_user_id',true)))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true)
    AND (NOT private OR actor_id::text=current_setting('tm.note_user_id',true)));
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v60;
-- Querying the RLS-filtered private bundle table with NOT EXISTS would hide
-- the very row that should deny a peer; keep a project-scoped carrier ACL fact.
CREATE TABLE data_private_carriers (
    project_id uuid NOT NULL REFERENCES projects(id), kind text NOT NULL CHECK(kind IN ('artifact','upload')),
    carrier_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
    PRIMARY KEY(project_id,kind,carrier_id,actor_id)
);
ALTER TABLE data_private_carriers ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_private_carriers FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON data_private_carriers USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true) AND actor_id::text=current_setting('tm.note_user_id',true));
CREATE FUNCTION private_data_carrier_visible(family text, identity uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT NOT EXISTS(SELECT 1 FROM data_private_carriers WHERE kind=family AND carrier_id=identity
        AND actor_id::text IS DISTINCT FROM current_setting('tm.note_user_id',true))
$$;
CREATE FUNCTION register_private_bundle_carrier() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.private THEN
        IF NEW.artifact_id IS NOT NULL THEN
            INSERT INTO data_private_carriers VALUES(NEW.project_id,'artifact',NEW.artifact_id,NEW.actor_id) ON CONFLICT DO NOTHING;
        ELSIF NEW.upload_id IS NOT NULL THEN
            INSERT INTO data_private_carriers VALUES(NEW.project_id,'upload',NEW.upload_id,NEW.actor_id) ON CONFLICT DO NOTHING;
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER private_bundle_carrier AFTER INSERT OR UPDATE ON experiment_bundles FOR EACH ROW EXECUTE FUNCTION register_private_bundle_carrier();
DROP POLICY project_boundary ON artifacts;
CREATE POLICY project_boundary ON artifacts USING(project_id::text=current_setting('tm.project_id',true)
    AND private_data_carrier_visible('artifact',id)
    AND (coalesce(metadata->>'private','false')<>'true' OR metadata->>'private_actor_id'=current_setting('tm.note_user_id',true)))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true)
    AND (coalesce(metadata->>'private','false')<>'true' OR metadata->>'private_actor_id'=current_setting('tm.note_user_id',true)));
DROP POLICY project_boundary ON artifact_chunks;
CREATE POLICY project_boundary ON artifact_chunks USING(project_id::text=current_setting('tm.project_id',true)
    AND EXISTS(SELECT 1 FROM artifacts WHERE id=artifact_id))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true) AND EXISTS(SELECT 1 FROM artifacts WHERE id=artifact_id));
DROP POLICY project_boundary ON bundle_upload_chunks;
CREATE POLICY project_boundary ON bundle_upload_chunks USING(project_id::text=current_setting('tm.project_id',true)
    AND private_data_carrier_visible('upload',upload_id))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true) AND private_data_carrier_visible('upload',upload_id));
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; p jsonb; item jsonb; BEGIN
    IF (task_kind='data_export' AND task_params ? 'plan_id') OR task_kind IN ('data_restore','data_resume') THEN
        features:=ARRAY['worker.data_bundle_v1']; p:=task_params->'storage_policy';
        IF p->>'kind' IN ('filesystem','s3') THEN
            features:=array_append(features,'storage.target:'||(p->>'target_id')||':'||(p->>'config_revision')||'@'||(p->>'host_id'));
        END IF;
        FOR item IN SELECT value FROM jsonb_each(COALESCE(task_params->'restore_policies','{}'::jsonb)) LOOP
            IF item->>'kind' IN ('filesystem','s3') THEN
                features:=array_append(features,'storage.target:'||(item->>'target_id')||':'||(item->>'config_revision')||'@'||(item->>'host_id'));
            END IF;
        END LOOP;
        FOR item IN SELECT value FROM jsonb_array_elements(COALESCE(task_params->'source_targets','[]'::jsonb)) LOOP
            IF item->>'kind' IN ('filesystem','s3') THEN
                features:=array_append(features,'storage.target:'||(item->>'target_id')||':'||(item->>'config_revision')||'@'||(item->>'host_id'));
            END IF;
        END LOOP;
        IF task_kind='data_resume' THEN
            features:=features||ARRAY['worker.core','worker.backend:'||(task_params->>'backend'),task_params->>'kernel_feature'];
        END IF;
        IF task_kind='data_resume' AND task_params->>'adapter'='language' THEN features:=features||ARRAY['worker.language_v1']; END IF;
        RETURN features;
    END IF;
    RETURN required_job_features_v60(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(61);
