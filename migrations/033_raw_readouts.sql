SET search_path TO tm2,pg_catalog;

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v32;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; spec jsonb;
BEGIN
    features := required_job_features_v32(task_kind,task_run,task_params);
    IF task_kind IN ('run','research_plan') THEN
        SELECT runs.spec INTO spec FROM runs WHERE id=task_run;
    ELSIF task_kind='study' THEN
        spec := task_params->'protocol'->'base';
    END IF;
    IF spec IS NOT NULL AND COALESCE((spec->'structural_readout'->>'enabled')::boolean,true)
        AND COALESCE((spec->'structural_readout'->>'read_touched_activity')::boolean,true) THEN
        features := array_append(features,'worker.raw_readout_v1');
    END IF;
    RETURN features;
END $$;

-- Re-evaluate waiting tasks. Leased tasks retain their recorded assignment;
-- their packets describe whether an unfiltered snapshot was actually saved.
DO $$ DECLARE project uuid;
BEGIN
    FOR project IN SELECT DISTINCT project_id FROM jobs WHERE status='pending' LOOP
        PERFORM set_config('tm.project_id',project::text,true);
        UPDATE jobs SET params=params WHERE project_id=project AND status='pending'
            AND kind IN ('run','study','research_plan');
    END LOOP;
    PERFORM set_config('tm.project_id','',true);
END $$;
INSERT INTO schema_version(version) VALUES(33);
