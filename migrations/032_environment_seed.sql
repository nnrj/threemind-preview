SET search_path TO tm2,pg_catalog;

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v31;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; spec jsonb;
BEGIN
    features := required_job_features_v31(task_kind,task_run,task_params);
    IF task_kind IN ('run','research_plan') THEN
        SELECT runs.spec INTO spec FROM runs WHERE id=task_run;
    ELSIF task_kind='study' THEN
        spec := task_params->'protocol'->'base';
    END IF;
    -- Even explicit null is a new field rejected by older strict RunSpec readers.
    -- Protocols stored before this addition remain eligible for old workers.
    IF spec ? 'environment_seed' THEN
        features := array_append(features,'worker.environment_seed_v1');
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(32);
