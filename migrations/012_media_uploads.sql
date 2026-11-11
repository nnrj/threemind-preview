SET search_path = tm2, pg_catalog;
CREATE TABLE media_uploads (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id), run_id uuid NOT NULL REFERENCES runs(id),
    actor_id uuid NOT NULL REFERENCES users(id), metadata jsonb NOT NULL, request_hash text NOT NULL,
    byte_length bigint NOT NULL CHECK(byte_length > 0), received_bytes bigint NOT NULL DEFAULT 0,
    next_chunk integer NOT NULL DEFAULT 0, status text NOT NULL DEFAULT 'uploading'
        CHECK(status IN ('uploading','processing','cancel_requested','failed','cancelled','accepted','expired')),
    stage text NOT NULL DEFAULT 'uploading', progress_bytes bigint NOT NULL DEFAULT 0,
    progress_frames bigint NOT NULL DEFAULT 0, sha256 text, error text, receipt jsonb,
    expires_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,run_id,id), FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    CHECK(received_bytes >= 0 AND received_bytes <= byte_length), CHECK(next_chunk >= 0)
);
CREATE INDEX media_uploads_run ON media_uploads(run_id,created_at,id);
CREATE INDEX media_uploads_expiry ON media_uploads(project_id,expires_at) WHERE status NOT IN ('accepted','cancelled','expired');
CREATE TABLE media_upload_chunks (
    project_id uuid NOT NULL, run_id uuid NOT NULL, upload_id uuid NOT NULL,
    chunk_index integer NOT NULL CHECK(chunk_index >= 0), sha256 text NOT NULL,
    body bytea NOT NULL CHECK(octet_length(body) > 0 AND octet_length(body) <= 1048576),
    PRIMARY KEY(upload_id,chunk_index),
    FOREIGN KEY(project_id,run_id,upload_id) REFERENCES media_uploads(project_id,run_id,id) ON DELETE CASCADE
);
ALTER TABLE media_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_uploads FORCE ROW LEVEL SECURITY;
ALTER TABLE media_upload_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_upload_chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON media_uploads USING(project_id::text=current_setting('tm.project_id',true)) WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE POLICY project_boundary ON media_upload_chunks USING(project_id::text=current_setting('tm.project_id',true)) WITH CHECK(project_id::text=current_setting('tm.project_id',true));
INSERT INTO schema_version(version) VALUES(12);
