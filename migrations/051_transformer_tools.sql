SET search_path TO tm2,pg_catalog;
-- Only dispatch metadata changes. No model conversion, historical scan or backfill.
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v50;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; identity text;
BEGIN
    IF task_kind='transformer' THEN RETURN ARRAY['worker.transformer_v1']; END IF;
    features := required_job_features_v50(task_kind,task_run,task_params);
    IF task_kind='study' THEN identity := task_params#>>'{protocol,base,kernel_id}';
    ELSIF task_kind='ecology' THEN
        SELECT protocol#>>'{base,kernel_id}' INTO identity FROM ecology_campaigns WHERE id=(task_params->>'campaign_id')::uuid;
    ELSIF task_run IS NOT NULL THEN SELECT spec->>'kernel_id' INTO identity FROM runs WHERE id=task_run;
    END IF;
    IF identity='threemind.continuous/1' THEN features := array_append(features,'worker.kernel_continuous1'); END IF;
    IF identity='threemind.lif/1' THEN features := array_append(features,'worker.kernel_lif1'); END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(51);
