SET search_path TO tm2,pg_catalog;

ALTER TABLE report_source_requests DROP CONSTRAINT report_source_requests_kind_check;
ALTER TABLE report_source_requests ADD CHECK(kind IN ('trajectory','nodes','edges','analysis','events','evolution',
    'ecology_trajectory','ecology_members','assessment','temporal_windows','temporal_nodes','temporal_series')) NOT VALID;
ALTER TABLE report_source_requests ADD COLUMN calibration_id uuid;
ALTER TABLE report_source_requests ADD FOREIGN KEY(project_id,calibration_id) REFERENCES probe_calibrations(project_id,id) NOT VALID;

-- No historical data scan, backfill, job rewrite or model conversion.
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v49;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind='probe_calibration' AND task_params->>'observation_mode'='temporal' THEN
        RETURN ARRAY['worker.core','worker.temporal_probe_v1'];
    END IF;
    IF task_kind='report_source' AND task_params->>'source_kind' IN ('temporal_windows','temporal_nodes','temporal_series') THEN
        RETURN ARRAY['worker.temporal_reports_v1'];
    END IF;
    RETURN required_job_features_v49(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(50);
