SET search_path TO tm2,pg_catalog;
ALTER TABLE report_source_requests DROP CONSTRAINT report_source_requests_kind_check;
ALTER TABLE report_source_requests ADD CHECK(kind IN ('trajectory','nodes','edges','analysis','events','evolution'));
ALTER TABLE report_source_requests ADD COLUMN evolution_id uuid;
ALTER TABLE report_source_requests ADD FOREIGN KEY(project_id,evolution_id) REFERENCES evolution_campaigns(project_id,id);
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v34;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind='evolution_export' THEN RETURN ARRAY['worker.evolution_v1']; END IF;
    IF task_kind='report_source' AND task_params->>'source_kind'='evolution' THEN
        RETURN array_append(required_job_features_v34(task_kind,task_run,task_params),'worker.evolution_v1');
    END IF;
    RETURN required_job_features_v34(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(35);
