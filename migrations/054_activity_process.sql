SET search_path TO tm2,pg_catalog;

-- Observer versioning only. No Core, old checkpoint or historical result rewrite.
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v53;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; source_spec jsonb;
BEGIN
    features := required_job_features_v53(task_kind,task_run,task_params);
    IF task_run IS NOT NULL THEN SELECT spec INTO source_spec FROM runs WHERE id=task_run; END IF;
    IF jsonb_path_exists(COALESCE(source_spec,'{}'::jsonb), '$.**.activity_readout ? (@.analysis_version == 2 && @.enabled == true)')
        OR jsonb_path_exists(COALESCE(task_params,'{}'::jsonb), '$.**.activity_readout ? (@.analysis_version == 2 && @.enabled == true)') THEN
        features := array_append(features,'worker.activity_analysis_v2');
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(54);
