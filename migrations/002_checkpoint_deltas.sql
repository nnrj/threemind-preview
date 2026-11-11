SET search_path = tm2, pg_catalog;

ALTER TABLE checkpoints
    ADD COLUMN storage_format text NOT NULL DEFAULT 'tmind/2',
    ADD COLUMN base_checkpoint_id uuid,
    ADD COLUMN delta_depth integer NOT NULL DEFAULT 0,
    ADD CONSTRAINT checkpoints_project_run_id UNIQUE(project_id,run_id,id),
    ADD CONSTRAINT checkpoints_delta_base FOREIGN KEY(project_id,run_id,base_checkpoint_id)
        REFERENCES checkpoints(project_id,run_id,id) DEFERRABLE INITIALLY DEFERRED,
    ADD CONSTRAINT checkpoints_storage CHECK (
        (storage_format='tmind/2' AND base_checkpoint_id IS NULL AND delta_depth=0) OR
        (storage_format='row-delta/1' AND base_checkpoint_id IS NOT NULL AND delta_depth BETWEEN 1 AND 8)
    );
CREATE INDEX checkpoints_base ON checkpoints(base_checkpoint_id) WHERE base_checkpoint_id IS NOT NULL;
INSERT INTO schema_version(version) VALUES(2);
