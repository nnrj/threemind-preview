SET search_path TO tm2,pg_catalog;
-- A published artifact's content and scientific metadata remain immutable.
-- Only the physical pointer may move to the exact same bytes; this does not
-- change the publication, its original chunks, identity or fixed hashes.
CREATE OR REPLACE FUNCTION preserve_shared_artifact() RETURNS trigger LANGUAGE plpgsql AS $$
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
        IF TG_TABLE_NAME='artifacts' AND TG_OP='UPDATE' THEN
            IF NEW.blob_id IS DISTINCT FROM OLD.blob_id
               AND (to_jsonb(NEW)-'blob_id') IS NOT DISTINCT FROM (to_jsonb(OLD)-'blob_id') THEN
                IF NEW.blob_id IS NOT NULL AND EXISTS(
                    SELECT 1 FROM stored_blobs b WHERE b.id=NEW.blob_id AND b.project_id=OLD.project_id
                        AND b.bytes=OLD.bytes AND b.sha256=OLD.sha256
                ) THEN
                    RETURN NEW;
                ELSIF NEW.blob_id IS NULL AND OLD.bytes=(
                    SELECT coalesce(sum(octet_length(body)),0) FROM artifact_chunks WHERE artifact_id=OLD.id
                ) THEN
                    -- The migration service verifies retained chunk hashes before
                    -- rollback; the chunks themselves are still immutable here.
                    RETURN NEW;
                END IF;
            END IF;
        END IF;
        RAISE EXCEPTION 'published artifact bytes and metadata are immutable; placement requires identical content'
            USING ERRCODE='55000';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
INSERT INTO schema_version(version) VALUES(65);
