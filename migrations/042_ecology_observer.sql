SET search_path TO tm2,pg_catalog;

-- Independent observer work waits in the existing durable task queue.
ALTER TABLE jobs ADD COLUMN available_at timestamptz NOT NULL DEFAULT '1970-01-01 00:00:00+00';

CREATE TABLE ecology_observer_revisions (
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision>0),
    configuration jsonb NOT NULL,
    configuration_hash text NOT NULL,
    first_checkpoint_revision bigint NOT NULL CHECK(first_checkpoint_revision>0),
    actor_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(campaign_id,revision), UNIQUE(project_id,campaign_id,revision),
    FOREIGN KEY(project_id,campaign_id) REFERENCES ecology_campaigns(project_id,id)
);
CREATE TABLE ecology_observers (
    campaign_id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    revision bigint NOT NULL,
    next_checkpoint_revision bigint NOT NULL CHECK(next_checkpoint_revision>0),
    after_event_index integer NOT NULL DEFAULT -1 CHECK(after_event_index>=-1),
    rule_state jsonb NOT NULL DEFAULT '{}',
    job_id uuid,
    last_checkpoint_id uuid,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(project_id,campaign_id,revision) REFERENCES ecology_observer_revisions(project_id,campaign_id,revision),
    FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id),
    FOREIGN KEY(project_id,campaign_id,last_checkpoint_id) REFERENCES ecology_checkpoints(project_id,campaign_id,id)
);
CREATE TABLE ecology_observer_entries (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id uuid NOT NULL,
    campaign_id uuid NOT NULL,
    configuration_revision bigint NOT NULL,
    checkpoint_id uuid NOT NULL,
    entry_key text NOT NULL,
    kind text NOT NULL CHECK(kind IN ('event','summary','warning')),
    body jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(campaign_id,configuration_revision,checkpoint_id,entry_key),
    FOREIGN KEY(project_id,campaign_id,configuration_revision) REFERENCES ecology_observer_revisions(project_id,campaign_id,revision),
    FOREIGN KEY(project_id,campaign_id,checkpoint_id) REFERENCES ecology_checkpoints(project_id,campaign_id,id)
);
CREATE INDEX ecology_observer_feed ON ecology_observer_entries(campaign_id,configuration_revision,id DESC);
CREATE INDEX ecology_observer_waiting_jobs ON jobs((params->>'campaign_id'))
WHERE kind='ecology_observe' AND status IN ('pending','leased');
DO $$ DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['ecology_observer_revisions','ecology_observers','ecology_observer_entries'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
        EXECUTE format('CREATE POLICY project_scope ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',t);
    END LOOP;
    FOREACH t IN ARRAY ARRAY['ecology_observer_revisions','ecology_observer_entries'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_observer BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION preserve_ecology_record()',t);
    END LOOP;
END $$;
-- New committed evidence wakes dormant subscriptions in the same transaction.
-- No polling lease/receipt is produced while there is nothing new to describe.
CREATE FUNCTION wake_ecology_observers() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE jobs SET available_at=clock_timestamp()
    WHERE kind='ecology_observe' AND status IN ('pending','leased')
      AND params->>'campaign_id'=NEW.campaign_id::text;
    RETURN NEW;
END $$;
CREATE TRIGGER wake_observers AFTER INSERT ON ecology_checkpoints
FOR EACH ROW EXECUTE FUNCTION wake_ecology_observers();
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v41;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind='ecology_observe' THEN RETURN ARRAY['worker.ecology_observer_v1']; END IF;
    RETURN required_job_features_v41(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(42);
