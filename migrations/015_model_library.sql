SET search_path = tm2, pg_catalog;

ALTER TABLE runs
    ADD COLUMN description text NOT NULL DEFAULT '',
    ADD COLUMN tags text[] NOT NULL DEFAULT '{}',
    ADD COLUMN metadata_revision bigint NOT NULL DEFAULT 0,
    ADD COLUMN archived_at timestamptz,
    ADD COLUMN origin_checkpoint_id uuid,
    ADD COLUMN origin_kind text CHECK(origin_kind IN ('created','imported','fork','inherited','paired')),
    ADD CONSTRAINT runs_origin_checkpoint FOREIGN KEY(project_id,parent_id,origin_checkpoint_id)
        REFERENCES checkpoints(project_id,run_id,id),
    ADD CONSTRAINT runs_origin_parent CHECK(origin_checkpoint_id IS NULL OR parent_id IS NOT NULL),
    ADD CONSTRAINT runs_metadata_bounds CHECK(length(description)<=20000 AND cardinality(tags)<=20);
CREATE INDEX runs_library ON runs(project_id,archived_at,created_at DESC,id);
CREATE INDEX runs_tags ON runs USING gin(tags);
ALTER TABLE checkpoints
    ADD COLUMN label text NOT NULL DEFAULT '',
    ADD COLUMN notes text NOT NULL DEFAULT '',
    ADD COLUMN tags text[] NOT NULL DEFAULT '{}',
    ADD COLUMN pinned boolean NOT NULL DEFAULT false,
    ADD COLUMN metadata_revision bigint NOT NULL DEFAULT 0,
    ADD CONSTRAINT checkpoints_metadata_bounds CHECK(length(label)<=120 AND length(notes)<=20000 AND cardinality(tags)<=20);

CREATE TABLE model_metadata_history (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id uuid NOT NULL, run_id uuid NOT NULL, checkpoint_id uuid,
    metadata_revision bigint NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
    before_value jsonb NOT NULL, after_value jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id,checkpoint_id) REFERENCES checkpoints(project_id,run_id,id) ON DELETE CASCADE
);
CREATE INDEX model_metadata_page ON model_metadata_history(run_id,id DESC);
CREATE TABLE model_cleanup_log (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    removed_run_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
    summary jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

-- Carrier references become real foreign keys before any asset reclamation is offered.
-- The envelope is inserted before its binary asset in the same existing transaction.
ALTER TABLE input_envelopes
    ADD COLUMN asset_sha256 text GENERATED ALWAYS AS (payload->>'asset_sha256') STORED,
    ADD CONSTRAINT input_asset_reference FOREIGN KEY(project_id,asset_sha256)
        REFERENCES media_assets(project_id,sha256) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX input_asset_reference ON input_envelopes(project_id,asset_sha256) WHERE asset_sha256 IS NOT NULL;

DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['model_metadata_history','model_cleanup_log'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',t);
    END LOOP;
END $$;
INSERT INTO schema_version(version) VALUES(15);
