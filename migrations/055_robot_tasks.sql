SET search_path TO tm2,pg_catalog;

-- Dispatch only: no edits to old models, snapshots or evidence.
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v54;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; source_spec jsonb; robot jsonb; sources jsonb;
BEGIN
    features := required_job_features_v54(task_kind,task_run,task_params);
    IF task_run IS NOT NULL THEN SELECT spec INTO source_spec FROM runs WHERE id=task_run; END IF;
    sources := jsonb_build_array(COALESCE(source_spec,'{}'::jsonb),COALESCE(task_params,'{}'::jsonb));
    FOR robot IN SELECT value FROM jsonb_path_query(sources, '$.**.robot_protocol ? (@.schema_id == "threemind.robot-task/1")') AS q(value) LOOP
        features := array_append(features,'worker.robot_v1');
        IF robot->>'asset_id' IS NOT NULL THEN
            features := array_append(features,'worker.robot_asset_' || (robot->>'asset_id'));
        END IF;
        IF EXISTS(SELECT 1 FROM jsonb_array_elements(robot#>'{world,sensors}') s WHERE s->>'kind'='camera_rgb') THEN
            features := array_append(features,'worker.world_rgb_v1');
        END IF;
    END LOOP;
    RETURN ARRAY(SELECT DISTINCT unnest(features));
END $$;
INSERT INTO schema_version(version) VALUES(55);
