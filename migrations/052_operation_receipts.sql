SET search_path TO tm2,pg_catalog;
-- Request receipts only; no model rewrite, historical scan or data conversion.
CREATE TABLE operation_receipts (
    project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    request_id uuid NOT NULL,
    fingerprint text NOT NULL,
    method text NOT NULL,
    path text NOT NULL,
    status text NOT NULL CHECK(status IN ('pending','completed','unknown')),
    response_status integer,
    response jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,actor_id,request_id)
);
ALTER TABLE operation_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE operation_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON operation_receipts
 USING(project_id::text=current_setting('tm.project_id',true))
 WITH CHECK(project_id::text=current_setting('tm.project_id',true));
INSERT INTO schema_version(version) VALUES(52);
