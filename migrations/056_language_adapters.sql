SET search_path TO tm2,pg_catalog;

CREATE TABLE language_sessions (
    run_id uuid PRIMARY KEY, project_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
    fingerprint text NOT NULL, protocol jsonb NOT NULL, compute jsonb NOT NULL, assets jsonb NOT NULL,
    head_artifact_id uuid GENERATED ALWAYS AS ((assets->>'head')::uuid) STORED,
    input_artifact_id uuid GENERATED ALWAYS AS ((assets->>'input')::uuid) STORED,
    output_artifact_id uuid GENERATED ALWAYS AS ((assets->>'output')::uuid) STORED,
    source_run_id uuid, source_checkpoint_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,source_run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,source_checkpoint_id) REFERENCES checkpoints(project_id,id),
    FOREIGN KEY(project_id,head_artifact_id) REFERENCES artifacts(project_id,id),
    FOREIGN KEY(project_id,input_artifact_id) REFERENCES artifacts(project_id,id),
    FOREIGN KEY(project_id,output_artifact_id) REFERENCES artifacts(project_id,id)
);
CREATE TABLE language_turns (
    job_id uuid PRIMARY KEY REFERENCES jobs(id), project_id uuid NOT NULL, run_id uuid NOT NULL,
    expected_revision bigint NOT NULL, text text NOT NULL, intensity double precision NOT NULL,
    result jsonb, result_checkpoint_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,result_checkpoint_id) REFERENCES checkpoints(project_id,id)
);
CREATE INDEX language_turns_timeline ON language_turns(run_id,created_at DESC,job_id);
ALTER TABLE language_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE language_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY language_sessions_project ON language_sessions USING(project_id::text=current_setting('tm.project_id',true));
ALTER TABLE language_turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE language_turns FORCE ROW LEVEL SECURITY;
CREATE POLICY language_turns_project ON language_turns USING(project_id::text=current_setting('tm.project_id',true));

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v55;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; p jsonb;
BEGIN
    features := required_job_features_v55(task_kind,task_run,task_params);
    IF task_kind='transformer' AND task_params->>'operation' LIKE 'language_%' THEN
        features := array_remove(features,'worker.transformer_v1');
        features := array_append(features,'worker.language_v1');
        IF task_run IS NOT NULL THEN
            features := features || required_job_features_v55('run',task_run,'{}'::jsonb);
        END IF;
        p := COALESCE(task_params->'protocol',task_params#>'{training,protocol}');
        IF task_params->>'operation' IN ('language_train','language_scratch_train')
           OR p->>'input_model' IN ('qwen','scratch') OR p->>'output_model' IN ('qwen','scratch') THEN
            features := array_append(features,'worker.language_torch_v1');
        END IF;
        IF p->>'input_model'='qwen' THEN features := array_append(features,'worker.language_embedding'); END IF;
        IF p->>'output_model'='qwen' THEN features := array_append(features,'worker.language_decoder'); END IF;
    END IF;
    RETURN ARRAY(SELECT DISTINCT unnest(features));
END $$;
INSERT INTO schema_version(version) VALUES(56);
