SET search_path TO tm2,pg_catalog;

CREATE TABLE evolution_campaigns (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    name text NOT NULL,
    objective text NOT NULL,
    protocol jsonb NOT NULL,
    protocol_hash text NOT NULL,
    job_id uuid NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','blocked','completed','cancelled')),
    phase text NOT NULL DEFAULT 'birth' CHECK(phase IN ('birth','development','evaluation','verification','complete')),
    generation integer NOT NULL DEFAULT 0 CHECK(generation>=0),
    wave integer NOT NULL DEFAULT 0 CHECK(wave>=0),
    revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
    error text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id), UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id)
);
CREATE TABLE evolution_members (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    generation integer NOT NULL CHECK(generation>=0),
    wave integer NOT NULL CHECK(wave>0),
    slot integer NOT NULL CHECK(slot>=0),
    stage text NOT NULL CHECK(stage IN ('development','evaluation','verification')),
    block_index integer NOT NULL CHECK(block_index>=0),
    environment_seed bigint NOT NULL CHECK(environment_seed BETWEEN 0 AND 4294967295),
    run_id uuid NOT NULL UNIQUE,
    source_version_id uuid,
    candidate_version_id uuid,
    checkpoint_id uuid,
    state_hash text,
    outcome jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id), UNIQUE(campaign_id,generation,stage,slot,block_index),
    FOREIGN KEY(project_id,campaign_id) REFERENCES evolution_campaigns(project_id,id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,source_version_id) REFERENCES innate_versions(project_id,id),
    FOREIGN KEY(project_id,candidate_version_id) REFERENCES innate_versions(project_id,id),
    FOREIGN KEY(project_id,checkpoint_id) REFERENCES checkpoints(project_id,id),
    CHECK((checkpoint_id IS NULL AND state_hash IS NULL AND outcome IS NULL) OR
          (checkpoint_id IS NOT NULL AND state_hash IS NOT NULL AND outcome IS NOT NULL))
);
CREATE TABLE evolution_selections (
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    generation integer NOT NULL,
    slot integer NOT NULL,
    candidate_version_id uuid NOT NULL,
    rank integer NOT NULL CHECK(rank>0),
    selected boolean NOT NULL,
    scores jsonb NOT NULL,
    evidence jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(campaign_id,generation,slot),
    UNIQUE(campaign_id,generation,rank),
    FOREIGN KEY(project_id,campaign_id) REFERENCES evolution_campaigns(project_id,id),
    FOREIGN KEY(project_id,candidate_version_id) REFERENCES innate_versions(project_id,id)
);
CREATE TABLE evolution_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    revision bigint NOT NULL,
    kind text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(campaign_id,revision),
    FOREIGN KEY(project_id,campaign_id) REFERENCES evolution_campaigns(project_id,id)
);
CREATE INDEX evolution_recent ON evolution_campaigns(project_id,created_at DESC,id DESC);
CREATE INDEX evolution_wave ON evolution_members(campaign_id,wave,slot,block_index);

CREATE FUNCTION preserve_evolution_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'evolution provenance cannot be deleted' USING ERRCODE='55000';
    END IF;
    IF TG_TABLE_NAME='evolution_campaigns' THEN
        IF (to_jsonb(NEW)-ARRAY['status','phase','generation','wave','revision','error','updated_at']) IS DISTINCT FROM
           (to_jsonb(OLD)-ARRAY['status','phase','generation','wave','revision','error','updated_at']) THEN
            RAISE EXCEPTION 'evolution protocol is immutable' USING ERRCODE='55000';
        END IF;
    ELSIF TG_TABLE_NAME='evolution_members' THEN
        IF OLD.checkpoint_id IS NOT NULL OR
           (to_jsonb(NEW)-ARRAY['candidate_version_id','checkpoint_id','state_hash','outcome']) IS DISTINCT FROM
           (to_jsonb(OLD)-ARRAY['candidate_version_id','checkpoint_id','state_hash','outcome']) THEN
            RAISE EXCEPTION 'evolution member identity and committed outcome are immutable' USING ERRCODE='55000';
        END IF;
    ELSE
        RAISE EXCEPTION 'evolution selection and event evidence are immutable' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END $$;
DO $$ DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['evolution_campaigns','evolution_members','evolution_selections','evolution_events'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format('CREATE POLICY project_scope ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',table_name);
        EXECUTE format('CREATE TRIGGER immutable_evolution BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_evolution_record()',table_name);
    END LOOP;
END $$;

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v33;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[];
BEGIN
    IF task_kind='evolution' THEN RETURN ARRAY['worker.evolution_v1']; END IF;
    features := required_job_features_v33(task_kind,task_run,task_params);
    IF task_kind='run' AND EXISTS(SELECT 1 FROM evolution_members WHERE run_id=task_run) THEN
        features := array_append(features,'worker.evolution_v1');
    END IF;
    RETURN features;
END $$;
INSERT INTO schema_version(version) VALUES(34);
