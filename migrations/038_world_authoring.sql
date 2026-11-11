SET search_path TO tm2,pg_catalog;

ALTER TABLE world_versions ADD COLUMN ai_call_id uuid,
    ADD COLUMN ai_protocol_hash text,
    ADD CONSTRAINT world_ai_provenance_pair CHECK((ai_call_id IS NULL)=(ai_protocol_hash IS NULL)),
    ADD CONSTRAINT world_ai_call_scope FOREIGN KEY(project_id,ai_call_id) REFERENCES ai_calls(project_id,id);

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v37;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[];
BEGIN
    features := required_job_features_v37(task_kind,task_run,task_params);
    IF task_kind='ai' AND task_params->>'purpose'='world' THEN
        features := array_append(features,'worker.world_authoring_v1');
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(38);
