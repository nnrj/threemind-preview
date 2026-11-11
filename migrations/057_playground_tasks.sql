SET search_path TO tm2,pg_catalog;

-- Optional external physics only; old task requirements remain unchanged.
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v56;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; source_spec jsonb; robot jsonb; sources jsonb;
BEGIN
    features := required_job_features_v56(task_kind,task_run,task_params);
    IF task_run IS NOT NULL THEN SELECT spec INTO source_spec FROM runs WHERE id=task_run; END IF;
    sources := jsonb_build_array(COALESCE(source_spec,'{}'::jsonb),COALESCE(task_params,'{}'::jsonb));
    FOR robot IN SELECT value FROM jsonb_path_query(sources, '$.**.robot_protocol ? (@.schema_id == "threemind.robot-task/2")') AS q(value) LOOP
        features := array_append(features,'worker.playground_' || COALESCE(robot#>>'{playground,implementation}','jax') || '_' || COALESCE(robot#>>'{playground,device}','cpu'));
    END LOOP;
    -- Capabilities are a set. Canonical ordering keeps admission refreshes and
    -- their receipts stable even when PostgreSQL chooses a different plan.
    RETURN ARRAY(SELECT DISTINCT f FROM unnest(features) AS f ORDER BY f);
END $$;
INSERT INTO schema_version(version) VALUES(57);
