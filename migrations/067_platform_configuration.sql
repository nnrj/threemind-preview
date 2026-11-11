SET search_path=tm2,pg_catalog;
SELECT set_config('tm.ai_admin','true',true);
SELECT set_config('tm.platform_superadmin','true',true);

-- Host configuration only: no changes to scientific definitions or checkpoints.
CREATE TABLE platform_creation_defaults (
    kernel_id text PRIMARY KEY, spec jsonb NOT NULL, revision bigint NOT NULL CHECK(revision>0),
    updated_by uuid NOT NULL REFERENCES users(id), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE platform_creation_default_versions (
    kernel_id text NOT NULL, revision bigint NOT NULL, spec jsonb NOT NULL,
    actor_id uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(kernel_id,revision)
);
CREATE TABLE creation_templates (
    id uuid PRIMARY KEY, name text NOT NULL, spec jsonb NOT NULL,
    revision bigint NOT NULL DEFAULT 1, created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), archived boolean NOT NULL DEFAULT false
);
CREATE TABLE creation_template_versions (
    template_id uuid NOT NULL REFERENCES creation_templates(id), revision bigint NOT NULL,
    name text NOT NULL, spec jsonb NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(template_id,revision)
);
ALTER TABLE runs ADD COLUMN creation_source jsonb NOT NULL DEFAULT '{}';

-- A single platform service catalogue. Existing grants and provider identities
-- survive; the original project is provenance, never an implicit global grant.
ALTER TABLE ai_providers ADD COLUMN original_project_id uuid REFERENCES projects(id);
INSERT INTO ai_provider_grants(provider_id,project_id)
    SELECT id,project_id FROM ai_providers WHERE project_id IS NOT NULL ON CONFLICT DO NOTHING;
UPDATE ai_providers SET original_project_id=project_id,project_id=NULL WHERE project_id IS NOT NULL;
CREATE TABLE ai_provider_versions (
    provider_id uuid NOT NULL REFERENCES ai_providers(id), revision bigint NOT NULL,
    config jsonb NOT NULL, actor_id uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
    source text NOT NULL DEFAULT 'saved' CHECK(source IN ('saved','current_import','call_snapshot')),
    PRIMARY KEY(provider_id,revision)
);
INSERT INTO ai_provider_versions(provider_id,revision,config,actor_id,source)
    SELECT id,revision,config,created_by,'current_import' FROM ai_providers;
INSERT INTO ai_provider_versions(provider_id,revision,config,actor_id,created_at,source)
    SELECT DISTINCT ON (provider_id,provider_revision) provider_id,provider_revision,provider_config,actor_id,created_at,'call_snapshot'
    FROM ai_calls ORDER BY provider_id,provider_revision,created_at ON CONFLICT DO NOTHING;
ALTER TABLE ai_calls ALTER COLUMN project_id DROP NOT NULL;
ALTER TABLE jobs ALTER COLUMN project_id DROP NOT NULL;
ALTER TABLE job_assignments ALTER COLUMN project_id DROP NOT NULL;
ALTER TABLE ai_calls ADD CONSTRAINT platform_diagnostic_scope CHECK(project_id IS NOT NULL OR (purpose='provider_test' AND run_id IS NULL));
ALTER TABLE jobs ADD CONSTRAINT platform_job_scope CHECK(project_id IS NOT NULL OR (kind='ai' AND run_id IS NULL));
CREATE UNIQUE INDEX ai_platform_requests ON ai_calls(actor_id,request_id) WHERE project_id IS NULL;
CREATE POLICY platform_diagnostic_access ON ai_calls USING(project_id IS NULL AND current_setting('tm.ai_admin',true)='true')
    WITH CHECK(project_id IS NULL AND current_setting('tm.ai_admin',true)='true');
CREATE POLICY platform_diagnostic_assignment ON job_assignments USING(project_id IS NULL AND current_setting('tm.ai_admin',true)='true')
    WITH CHECK(project_id IS NULL AND current_setting('tm.ai_admin',true)='true');

-- Original project settings/versions and delivery outbox remain untouched.
CREATE TABLE notification_services (
    id uuid PRIMARY KEY, name text NOT NULL, revision bigint NOT NULL DEFAULT 1,
    config jsonb NOT NULL, secrets text NOT NULL DEFAULT '',
    has_api_key boolean NOT NULL DEFAULT false, has_smtp_password boolean NOT NULL DEFAULT false,
    original_project_id uuid REFERENCES projects(id),
    created_by uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE notification_service_versions (
    service_id uuid NOT NULL REFERENCES notification_services(id), revision bigint NOT NULL,
    config jsonb NOT NULL, actor_id uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(service_id,revision)
);
CREATE TABLE notification_service_grants (
    service_id uuid NOT NULL REFERENCES notification_services(id), project_id uuid NOT NULL REFERENCES projects(id),
    granted_by uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(service_id,project_id)
);
CREATE TABLE notification_rule_bindings (
    project_id uuid PRIMARY KEY REFERENCES projects(id), service_id uuid REFERENCES notification_services(id),
    service_revision bigint, policy_revision bigint NOT NULL,
    updated_by uuid NOT NULL REFERENCES users(id), updated_at timestamptz NOT NULL DEFAULT now()
);
DO $$ DECLARE source record; service uuid; BEGIN
    FOR source IN SELECT s.*,p.name AS project_name FROM notification_settings s JOIN projects p ON p.id=s.project_id LOOP
        service := gen_random_uuid();
        INSERT INTO notification_services(id,name,revision,config,secrets,has_api_key,has_smtp_password,original_project_id,created_by)
            VALUES(service,source.project_name||' (imported)',1,
                source.config - ARRAY['enabled','email_enabled','language','ui_language','events','execution_health','recipients','cooldown_s','daily_email_limit'],
                source.secrets,source.has_api_key,source.has_smtp_password,source.project_id,source.actor_id);
        INSERT INTO notification_service_versions(service_id,revision,config,actor_id)
            SELECT service,1,config,source.actor_id FROM notification_services WHERE id=service;
        INSERT INTO notification_service_grants VALUES(service,source.project_id,source.actor_id,now());
        INSERT INTO notification_rule_bindings VALUES(source.project_id,service,1,source.revision,source.actor_id,now());
    END LOOP;
END $$;
-- AI reads persisted activity evidence. It does not run Core's activity
-- analysis and therefore must not request that simulation-worker capability.
ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v66;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$ DECLARE features text[]; BEGIN
    features := required_job_features_v66(task_kind,task_run,task_params);
    IF task_kind='ai' THEN features := array_remove(features,'worker.activity_analysis_v2'); END IF;
    RETURN features;
END $$;
UPDATE jobs SET required_features=array_remove(required_features,'worker.activity_analysis_v2') WHERE kind='ai' AND status='pending';
INSERT INTO schema_version(version) VALUES(67);
