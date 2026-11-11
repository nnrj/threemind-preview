SET search_path TO tm2,pg_catalog;

CREATE TABLE ecology_campaigns (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    operation_id uuid NOT NULL,
    request_hash text NOT NULL,
    name text NOT NULL,
    objective text NOT NULL,
    protocol jsonb NOT NULL,
    protocol_hash text NOT NULL,
    initial_version_id uuid,
    job_id uuid NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','blocked','completed','cancelled')),
    requested_action text CHECK(requested_action IN ('pause','cancel')),
    revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
    checkpoint_revision bigint NOT NULL DEFAULT 0 CHECK(checkpoint_revision>=0),
    checkpoint_id uuid,
    time_us numeric(39,0) NOT NULL DEFAULT 0 CHECK(time_us>=0),
    summary jsonb NOT NULL DEFAULT '{}',
    error text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id), UNIQUE(project_id,operation_id),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id),
    FOREIGN KEY(project_id,initial_version_id) REFERENCES innate_versions(project_id,id)
);
CREATE TABLE ecology_members (
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    individual text NOT NULL CHECK(individual ~ '^n[0-9]+$'),
    run_id uuid NOT NULL UNIQUE,
    parent text,
    generation integer NOT NULL CHECK(generation>=0),
    birth_us numeric(39,0) NOT NULL CHECK(birth_us>=0),
    birth_hash text NOT NULL,
    source_hash text NOT NULL,
    source_checkpoint_id uuid,
    PRIMARY KEY(campaign_id,individual),
    UNIQUE(project_id,campaign_id,individual),
    UNIQUE(project_id,campaign_id,individual,run_id),
    FOREIGN KEY(project_id,campaign_id) REFERENCES ecology_campaigns(project_id,id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id),
    FOREIGN KEY(project_id,campaign_id,parent) REFERENCES ecology_members(project_id,campaign_id,individual),
    FOREIGN KEY(project_id,source_checkpoint_id) REFERENCES checkpoints(project_id,id),
    CHECK((parent IS NULL AND generation=0) OR (parent IS NOT NULL AND generation>0))
);
CREATE TABLE ecology_checkpoints (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision>0),
    previous_id uuid,
    operation_id uuid NOT NULL,
    fingerprint text NOT NULL,
    state_hash text NOT NULL,
    time_us numeric(39,0) NOT NULL CHECK(time_us>=0),
    context jsonb NOT NULL,
    observation jsonb NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(project_id,id), UNIQUE(project_id,campaign_id,id),
    UNIQUE(campaign_id,revision), UNIQUE(campaign_id,operation_id),
    FOREIGN KEY(project_id,campaign_id) REFERENCES ecology_campaigns(project_id,id),
    FOREIGN KEY(project_id,campaign_id,previous_id) REFERENCES ecology_checkpoints(project_id,campaign_id,id)
);
ALTER TABLE ecology_campaigns ADD CONSTRAINT ecology_current_checkpoint
    FOREIGN KEY(project_id,id,checkpoint_id) REFERENCES ecology_checkpoints(project_id,campaign_id,id);
CREATE TABLE ecology_checkpoint_members (
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    population_checkpoint_id uuid NOT NULL,
    individual text NOT NULL,
    run_id uuid NOT NULL,
    checkpoint_id uuid NOT NULL,
    state_hash text NOT NULL,
    outcome jsonb NOT NULL,
    PRIMARY KEY(population_checkpoint_id,individual),
    FOREIGN KEY(project_id,campaign_id,population_checkpoint_id) REFERENCES ecology_checkpoints(project_id,campaign_id,id),
    FOREIGN KEY(project_id,campaign_id,individual,run_id) REFERENCES ecology_members(project_id,campaign_id,individual,run_id),
    FOREIGN KEY(project_id,checkpoint_id) REFERENCES checkpoints(project_id,id)
);
CREATE TABLE ecology_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    population_checkpoint_id uuid NOT NULL,
    event_index integer NOT NULL CHECK(event_index>=0),
    time_us numeric(39,0) NOT NULL,
    individual text,
    kind text NOT NULL,
    payload jsonb NOT NULL,
    UNIQUE(population_checkpoint_id,event_index),
    FOREIGN KEY(project_id,campaign_id,population_checkpoint_id) REFERENCES ecology_checkpoints(project_id,campaign_id,id),
    FOREIGN KEY(project_id,campaign_id,individual) REFERENCES ecology_members(project_id,campaign_id,individual)
);
CREATE INDEX ecology_recent ON ecology_campaigns(project_id,created_at DESC,id DESC);
CREATE INDEX ecology_checkpoint_history ON ecology_checkpoints(campaign_id,revision DESC);
CREATE INDEX ecology_member_history ON ecology_checkpoint_members(campaign_id,individual,population_checkpoint_id);
CREATE INDEX ecology_event_history ON ecology_events(campaign_id,id);

CREATE FUNCTION preserve_ecology_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='UPDATE' AND TG_TABLE_NAME='ecology_campaigns' THEN
        IF (to_jsonb(NEW)-ARRAY['status','requested_action','revision','checkpoint_revision','checkpoint_id','time_us','summary','error','updated_at']) IS NOT DISTINCT FROM
           (to_jsonb(OLD)-ARRAY['status','requested_action','revision','checkpoint_revision','checkpoint_id','time_us','summary','error','updated_at']) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'ecological protocols and committed evidence are immutable' USING ERRCODE='55000';
END $$;
DO $$ DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['ecology_campaigns','ecology_members','ecology_checkpoints','ecology_checkpoint_members','ecology_events'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
        EXECUTE format('CREATE POLICY project_scope ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',t);
        EXECUTE format('CREATE TRIGGER immutable_ecology BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_ecology_record()',t);
    END LOOP;
END $$;

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v38;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; spec jsonb; scope text;
BEGIN
    IF task_kind='ecology_export' THEN RETURN ARRAY['worker.ecology_v1']; END IF;
    IF task_kind='ecology' THEN
        spec := task_params->'base';
        features := ARRAY['worker.core','worker.ecology_v1','worker.world_v1'];
        IF EXISTS(SELECT 1 FROM jsonb_array_elements(spec->'world_protocol'->'sensors') s WHERE s->>'kind'='camera_rgb') THEN
            features := array_append(features,'worker.world_rgb_v1');
        END IF;
        IF coalesce((spec#>>'{source_policies,background_enabled}')::boolean,true) THEN
            FOREACH scope IN ARRAY ARRAY['host','process','runtime'] LOOP
                IF spec#>ARRAY[scope||'_telemetry','enabled']='true'::jsonb AND coalesce((spec#>>ARRAY['source_policies',scope||'_enabled'])::boolean,true) THEN
                    features := array_append(features,'worker.telemetry_'||scope);
                END IF;
            END LOOP;
        END IF;
        RETURN features;
    END IF;
    RETURN required_job_features_v38(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(39);
