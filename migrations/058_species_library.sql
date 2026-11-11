SET search_path TO tm2,pg_catalog;
CREATE TABLE species_assets (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    name text NOT NULL,
    bundle_hash text NOT NULL,
    manifest jsonb NOT NULL,
    bundle bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,bundle_hash),
    CHECK(octet_length(bundle)<=67108864)
);
ALTER TABLE species_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE species_assets FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON species_assets
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE INDEX species_assets_project_created ON species_assets(project_id,created_at DESC);
CREATE TRIGGER immutable_species_asset BEFORE UPDATE OR DELETE ON species_assets
    FOR EACH ROW EXECUTE FUNCTION preserve_research_evidence();
INSERT INTO schema_version(version) VALUES(58);
