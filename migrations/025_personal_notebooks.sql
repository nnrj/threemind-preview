SET search_path TO tm2,pg_catalog;

CREATE TABLE note_collections (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    owner_id uuid NOT NULL REFERENCES users(id),
    kind text NOT NULL CHECK(kind IN ('notebook','category')),
    name text NOT NULL,
    color text NOT NULL DEFAULT '#237969',
    is_default boolean NOT NULL DEFAULT false,
    auto_named boolean NOT NULL DEFAULT false,
    revision bigint NOT NULL DEFAULT 1,
    archived_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,owner_id,id),
    CHECK(NOT is_default OR kind='notebook')
);
CREATE UNIQUE INDEX default_notebook ON note_collections(project_id,owner_id) WHERE is_default;

CREATE TABLE notes (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    owner_id uuid NOT NULL REFERENCES users(id),
    title text NOT NULL,
    kind text NOT NULL CHECK(kind IN ('draft','note')),
    collection_id uuid,
    revision bigint NOT NULL,
    search_text text NOT NULL,
    archived_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,owner_id,id),
    FOREIGN KEY(project_id,owner_id,collection_id) REFERENCES note_collections(project_id,owner_id,id),
    CHECK(kind='draft' OR collection_id IS NOT NULL)
);

CREATE TABLE note_versions (
    project_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    note_id uuid NOT NULL,
    revision bigint NOT NULL,
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    metadata jsonb NOT NULL,
    body jsonb NOT NULL,
    content_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(note_id,revision),
    UNIQUE(note_id,operation_id),
    UNIQUE(project_id,owner_id,note_id,revision),
    FOREIGN KEY(project_id,owner_id,note_id) REFERENCES notes(project_id,owner_id,id)
);

CREATE TABLE note_assets (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    owner_id uuid NOT NULL REFERENCES users(id),
    name text NOT NULL,
    mime text NOT NULL,
    bytes bigint NOT NULL CHECK(bytes BETWEEN 1 AND 8388608),
    sha256 text NOT NULL,
    content bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,owner_id,id),
    CHECK(octet_length(content)=bytes)
);
CREATE TABLE note_asset_refs (
    project_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    note_id uuid NOT NULL,
    revision bigint NOT NULL,
    asset_id uuid NOT NULL,
    PRIMARY KEY(note_id,revision,asset_id),
    FOREIGN KEY(project_id,owner_id,note_id,revision) REFERENCES note_versions(project_id,owner_id,note_id,revision),
    FOREIGN KEY(project_id,owner_id,asset_id) REFERENCES note_assets(project_id,owner_id,id)
);
DO $$ DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['note_collections','notes','note_versions','note_assets','note_asset_refs'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY personal_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true) AND owner_id::text=current_setting(''tm.note_user_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true) AND owner_id::text=current_setting(''tm.note_user_id'',true))',relation);
    END LOOP;
END $$;
CREATE INDEX notes_personal_recent ON notes(project_id,owner_id,updated_at DESC,id DESC);
CREATE INDEX note_collections_personal ON note_collections(project_id,owner_id,kind,name,id);
CREATE INDEX note_assets_personal ON note_assets(project_id,owner_id,created_at DESC,id DESC);
CREATE FUNCTION preserve_note_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'saved note revisions and their references are immutable' USING ERRCODE='55000';
END $$;
CREATE TRIGGER preserve_note_versions BEFORE UPDATE OR DELETE ON note_versions
    FOR EACH ROW EXECUTE FUNCTION preserve_note_revision();
CREATE TRIGGER preserve_note_asset_refs BEFORE UPDATE OR DELETE ON note_asset_refs
    FOR EACH ROW EXECUTE FUNCTION preserve_note_revision();
CREATE TRIGGER preserve_note_assets BEFORE UPDATE ON note_assets
    FOR EACH ROW EXECUTE FUNCTION preserve_note_revision();
INSERT INTO schema_version(version) VALUES(25);
