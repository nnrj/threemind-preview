SET search_path TO tm2,pg_catalog;

-- Old workers may handle old language turns, but must not claim operations or
-- projection protocols they cannot interpret. No historical evidence changes.
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v58;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; protocol jsonb;
BEGIN
    features := required_job_features_v58(task_kind,task_run,task_params);
    IF task_kind='transformer' AND task_params->>'operation' LIKE 'language_%' THEN
        IF task_params->>'operation'='language_observe' THEN
            features := array_append(features,'worker.language_observation_v1');
        END IF;
        protocol := COALESCE(task_params->'protocol',task_params#>'{training,protocol}');
        IF protocol->>'schema_id'='threemind.language-adapter/2' THEN
            features := array_append(features,'worker.language_projection_v2');
        END IF;
    END IF;
    RETURN ARRAY(SELECT DISTINCT f FROM unnest(features) AS f ORDER BY f);
END $$;

-- Refresh only pending new operations in their project scopes, never old results.
DO $$ DECLARE project uuid;
BEGIN
    FOR project IN SELECT DISTINCT project_id FROM jobs WHERE status='pending'
        AND kind='transformer' AND params->>'operation' LIKE 'language_%' LOOP
        PERFORM set_config('tm.project_id',project::text,true);
        UPDATE jobs SET required_features=required_job_features(kind,run_id,params)
            WHERE project_id=project AND status='pending' AND kind='transformer'
            AND params->>'operation' LIKE 'language_%';
    END LOOP;
END $$;
INSERT INTO schema_version(version) VALUES(59);
