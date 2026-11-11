SET search_path TO tm2,pg_catalog;

CREATE TABLE notification_settings (
    project_id uuid PRIMARY KEY REFERENCES projects(id),
    revision bigint NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    config jsonb NOT NULL,
    secrets text NOT NULL DEFAULT '',
    has_api_key boolean NOT NULL DEFAULT false,
    has_smtp_password boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE notification_versions (
    project_id uuid NOT NULL REFERENCES projects(id),
    revision bigint NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id),
    config jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,revision)
);
CREATE TABLE notifications (
    id uuid PRIMARY KEY,
    ordinal bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    project_id uuid NOT NULL REFERENCES projects(id),
    run_id uuid,
    source_key text NOT NULL,
    kind text NOT NULL,
    facts jsonb NOT NULL,
    policy_revision bigint NOT NULL,
    email_status text NOT NULL DEFAULT 'disabled'
        CHECK(email_status IN ('disabled','queued','sending','sent','partial','failed','uncertain','cancelled','skipped')),
    email_reason text,
    email_provider_id text,
    email_job_id uuid,
    dispatched_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id),
    UNIQUE(project_id,source_key),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE SET NULL (run_id),
    FOREIGN KEY(project_id,email_job_id) REFERENCES jobs(project_id,id) ON DELETE SET NULL (email_job_id)
);
CREATE TABLE notification_reads (
    project_id uuid NOT NULL,
    notification_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(notification_id,user_id),
    FOREIGN KEY(project_id,notification_id) REFERENCES notifications(project_id,id) ON DELETE CASCADE
);
CREATE INDEX notifications_page ON notifications(project_id,ordinal DESC);
CREATE INDEX notifications_email_budget ON notifications(project_id,dispatched_at DESC) WHERE dispatched_at IS NOT NULL;
CREATE INDEX notification_reads_user ON notification_reads(project_id,user_id,notification_id);
CREATE INDEX jobs_queue_claim ON jobs((CASE WHEN kind IN ('ai','notification') THEN kind ELSE 'runtime' END),status,created_at);

DO $$ DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['notification_settings','notification_versions','notifications','notification_reads'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
        EXECUTE format('CREATE POLICY project_boundary ON %I USING(project_id::text=current_setting(''tm.project_id'',true)) WITH CHECK(project_id::text=current_setting(''tm.project_id'',true))',t);
    END LOOP;
END $$;

-- Transactional local outbox only. External delivery never runs in a trigger.
-- Unique source keys avoid duplicates; dispatch uses pending jobs, not a serial
-- high-water cursor which could miss a transaction that commits out of order.
CREATE FUNCTION emit_notification(p uuid, r uuid, source text, event_kind text, event_facts jsonb, force_test boolean DEFAULT false)
RETURNS uuid LANGUAGE plpgsql SET search_path = tm2,pg_catalog AS $$
DECLARE policy notification_settings%ROWTYPE; notice_id uuid; delivery_job uuid;
BEGIN
    SELECT * INTO policy FROM notification_settings WHERE project_id=p;
    IF NOT FOUND THEN RETURN NULL; END IF;
    IF NOT force_test AND (policy.config->>'enabled' IS DISTINCT FROM 'true'
        OR policy.config->'events'->>event_kind IS DISTINCT FROM 'true') THEN RETURN NULL; END IF;
    INSERT INTO notifications(id,project_id,run_id,source_key,kind,facts,policy_revision)
        VALUES(gen_random_uuid(),p,r,source,event_kind,event_facts,policy.revision)
        ON CONFLICT(project_id,source_key) DO NOTHING RETURNING id INTO notice_id;
    IF notice_id IS NULL THEN
        SELECT id INTO notice_id FROM notifications WHERE project_id=p AND source_key=source;
        RETURN notice_id;
    END IF;
    IF force_test OR policy.config->>'email_enabled'='true' THEN
        delivery_job := gen_random_uuid();
        -- No run job ownership: mailing does not keep a model execution busy.
        INSERT INTO jobs(id,project_id,kind,params)
            VALUES(delivery_job,p,'notification',jsonb_build_object('notification_id',notice_id));
        UPDATE notifications SET email_status='queued',email_job_id=delivery_job WHERE id=notice_id;
    END IF;
    RETURN notice_id;
END $$;

CREATE FUNCTION notify_run_transition() RETURNS trigger LANGUAGE plpgsql SET search_path=tm2,pg_catalog AS $$
BEGIN
    PERFORM emit_notification(NEW.project_id,NEW.id,'run:'||NEW.id||':'||NEW.status||':'||pg_current_xact_id(),
        'run_'||NEW.status,jsonb_build_object('run_name',NEW.name,'run_id',NEW.id,'status',NEW.status,
        'revision',NEW.revision,'time_us',NEW.time_us::text,'state_hash',NEW.state_hash,'life',NEW.life));
    RETURN NEW;
END $$;
CREATE TRIGGER notification_run_transition AFTER UPDATE OF status ON runs FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status AND NEW.status IN ('completed','failed','dead','blocked'))
    EXECUTE FUNCTION notify_run_transition();

CREATE FUNCTION notify_recurrence() RETURNS trigger LANGUAGE plpgsql SET search_path=tm2,pg_catalog AS $$
BEGIN
    PERFORM emit_notification(NEW.project_id,NEW.run_id,'event:'||NEW.id,'structure_recurrence',
        jsonb_build_object('event_id',NEW.id::text,'run_id',NEW.run_id,'time_us',NEW.time_us::text,
        'revision',NEW.commit_revision,'structure_id',NEW.payload->'structure'->'structure_id',
        'state_signature',NEW.payload->'structure'->'state_signature',
        'occurrences',NEW.payload->'structure'->'occurrences','span_us',NEW.payload->'structure'->'span_us'));
    RETURN NEW;
END $$;
CREATE TRIGGER notification_recurrence AFTER INSERT ON events FOR EACH ROW
    WHEN (NEW.kind='structural_readout' AND NEW.payload->'structure'->>'recurrence_notice'='true')
    EXECUTE FUNCTION notify_recurrence();

CREATE FUNCTION notify_job_finished() RETURNS trigger LANGUAGE plpgsql SET search_path=tm2,pg_catalog AS $$
DECLARE event_kind text;
BEGIN
    event_kind := CASE WHEN NEW.status='failed' THEN 'job_failed'
        WHEN NEW.kind='analysis' THEN 'analysis_ready' ELSE 'export_ready' END;
    PERFORM emit_notification(NEW.project_id,NEW.run_id,'job:'||NEW.id,event_kind,
        jsonb_build_object('job_id',NEW.id,'job_kind',NEW.kind,'run_id',NEW.run_id,'status',NEW.status,
        'artifact_id',NEW.result->'artifact_id','revision',NEW.result->'revision',
        'state_hash',NEW.result->'state_hash','study_id',NEW.params->'study_id'));
    RETURN NEW;
END $$;
CREATE TRIGGER notification_job_finished AFTER UPDATE OF status ON jobs FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status AND NEW.status IN ('done','failed')
        AND NEW.kind IN ('export','data_export','analysis')) EXECUTE FUNCTION notify_job_finished();

INSERT INTO schema_version(version) VALUES(21);
