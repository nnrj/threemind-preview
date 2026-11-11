SET search_path TO tm2,pg_catalog;

ALTER TABLE research_document_exports ADD UNIQUE(project_id,document_id,revision,id);
CREATE TABLE research_document_shares (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision bigint NOT NULL,
    export_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    body_artifact_id uuid NOT NULL,
    bundle_artifact_id uuid,
    metadata jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz,
    revoked_at timestamptz,
    UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,document_id,revision,export_id)
        REFERENCES research_document_exports(project_id,document_id,revision,id),
    FOREIGN KEY(project_id,body_artifact_id) REFERENCES artifacts(project_id,id),
    FOREIGN KEY(project_id,bundle_artifact_id) REFERENCES artifacts(project_id,id),
    CHECK(expires_at IS NULL OR expires_at>created_at)
);
ALTER TABLE research_document_shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_document_shares FORCE ROW LEVEL SECURITY;
CREATE POLICY project_scope ON research_document_shares
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
-- The resolver supplies one unguessable publication identifier, never a project scope.
-- This SELECT policy does not authorize inserts, updates, deletes or artifact access.
CREATE POLICY public_lookup ON research_document_shares FOR SELECT
    USING(id::text=current_setting('tm.shared_document_id',true));
CREATE INDEX research_shares_recent ON research_document_shares(project_id,document_id,created_at DESC,id DESC);
CREATE INDEX research_shares_body ON research_document_shares(body_artifact_id);
CREATE INDEX research_shares_bundle ON research_document_shares(bundle_artifact_id) WHERE bundle_artifact_id IS NOT NULL;

CREATE FUNCTION preserve_research_share() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' OR (to_jsonb(NEW)-'revoked_at') IS DISTINCT FROM (to_jsonb(OLD)-'revoked_at')
       OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at) THEN
        RAISE EXCEPTION 'published revisions are immutable; only permanent revocation is allowed' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_share BEFORE UPDATE OR DELETE ON research_document_shares
    FOR EACH ROW EXECUTE FUNCTION preserve_research_share();

CREATE FUNCTION preserve_shared_artifact() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_id uuid; new_id uuid;
BEGIN
    IF TG_TABLE_NAME='artifacts' THEN
        old_id:=OLD.id;
        IF TG_OP='UPDATE' THEN new_id:=NEW.id; END IF;
    ELSE
        IF TG_OP<>'INSERT' THEN old_id:=OLD.artifact_id; END IF;
        IF TG_OP<>'DELETE' THEN new_id:=NEW.artifact_id; END IF;
    END IF;
    IF EXISTS(SELECT 1 FROM research_document_shares
              WHERE body_artifact_id IN (old_id,new_id) OR bundle_artifact_id IN (old_id,new_id)) THEN
        RAISE EXCEPTION 'published artifact bytes and metadata are immutable' USING ERRCODE='55000';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_shared_artifact BEFORE UPDATE OR DELETE ON artifacts
    FOR EACH ROW EXECUTE FUNCTION preserve_shared_artifact();
CREATE TRIGGER immutable_shared_chunks BEFORE INSERT OR UPDATE OR DELETE ON artifact_chunks
    FOR EACH ROW EXECUTE FUNCTION preserve_shared_artifact();
INSERT INTO schema_version(version) VALUES(30);
