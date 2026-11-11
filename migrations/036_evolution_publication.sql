SET search_path TO tm2,pg_catalog;
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v35;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[];
BEGIN
    features := required_job_features_v35(task_kind,task_run,task_params);
    IF task_kind IN ('ai','report_export') AND task_params->>'evolution_evidence'='true' THEN
        features := array_append(features,'worker.evolution_v1');
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(36);
