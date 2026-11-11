SET search_path = tm2, pg_catalog;
CREATE TABLE project_run_defaults (
    project_id uuid PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    spec jsonb NOT NULL, revision bigint NOT NULL DEFAULT 1,
    updated_by uuid REFERENCES users(id), updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE project_run_defaults ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_run_defaults FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON project_run_defaults
    USING (project_id::text = current_setting('tm.project_id',true))
    WITH CHECK (project_id::text = current_setting('tm.project_id',true));
INSERT INTO schema_version(version) VALUES(3);
