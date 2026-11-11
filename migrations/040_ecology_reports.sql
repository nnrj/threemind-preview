SET search_path TO tm2,pg_catalog;
ALTER TABLE report_source_requests DROP CONSTRAINT report_source_requests_kind_check;
ALTER TABLE report_source_requests ADD CHECK(kind IN ('trajectory','nodes','edges','analysis','events','evolution','ecology_trajectory','ecology_members'));
ALTER TABLE report_source_requests ADD COLUMN ecology_id uuid;
ALTER TABLE report_source_requests ADD COLUMN ecology_checkpoint_id uuid;
ALTER TABLE report_source_requests ADD FOREIGN KEY(project_id,ecology_id,ecology_checkpoint_id) REFERENCES ecology_checkpoints(project_id,campaign_id,id);
ALTER TABLE report_source_requests ADD CHECK (
    (kind IN ('ecology_trajectory','ecology_members') AND ecology_id IS NOT NULL AND ecology_checkpoint_id IS NOT NULL)
    OR (kind NOT IN ('ecology_trajectory','ecology_members') AND ecology_id IS NULL AND ecology_checkpoint_id IS NULL)
);
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v39;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[];
BEGIN
    features := required_job_features_v39(task_kind,task_run,task_params);
    IF (task_kind='report_source' AND task_params->>'source_kind' IN ('ecology_trajectory','ecology_members'))
       OR (task_kind IN ('ai','report_export') AND task_params->>'ecology_evidence'='true') THEN
        features := array_append(features,'worker.ecology_evidence_v1');
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(40);
