SET search_path TO tm2,pg_catalog;
ALTER TABLE audit ADD COLUMN details jsonb NOT NULL DEFAULT '{}';

CREATE TABLE ai_providers (
    id uuid PRIMARY KEY,
    project_id uuid REFERENCES projects(id),
    revision bigint NOT NULL DEFAULT 1,
    config jsonb NOT NULL,
    secrets text NOT NULL,
    has_api_key boolean NOT NULL DEFAULT false,
    has_proxy_password boolean NOT NULL DEFAULT false,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ai_provider_grants (
    provider_id uuid NOT NULL REFERENCES ai_providers(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    PRIMARY KEY(provider_id,project_id)
);
ALTER TABLE ai_provider_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_provider_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY read_grants ON ai_provider_grants FOR SELECT USING (
    project_id::text=current_setting('tm.project_id',true) OR current_setting('tm.ai_admin',true)='true'
);
CREATE POLICY write_grants ON ai_provider_grants FOR ALL
    USING(current_setting('tm.ai_admin',true)='true') WITH CHECK(current_setting('tm.ai_admin',true)='true');
ALTER TABLE ai_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_providers FORCE ROW LEVEL SECURITY;
CREATE POLICY read_providers ON ai_providers FOR SELECT USING (
    project_id::text=current_setting('tm.project_id',true) OR current_setting('tm.ai_admin',true)='true'
    OR (project_id IS NULL AND EXISTS(SELECT 1 FROM ai_provider_grants g WHERE g.provider_id=id))
);
CREATE POLICY write_providers ON ai_providers FOR ALL
    USING(project_id::text=current_setting('tm.project_id',true) OR current_setting('tm.ai_admin',true)='true')
    WITH CHECK(project_id::text=current_setting('tm.project_id',true) OR current_setting('tm.ai_admin',true)='true');

CREATE TABLE ai_calls (
    id uuid PRIMARY KEY,
    ordinal bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    project_id uuid NOT NULL REFERENCES projects(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    provider_id uuid NOT NULL REFERENCES ai_providers(id),
    provider_revision bigint NOT NULL,
    provider_config jsonb NOT NULL,
    request_id uuid NOT NULL,
    fingerprint text NOT NULL,
    purpose text NOT NULL,
    run_id uuid,
    evidence jsonb NOT NULL DEFAULT '{}',
    prompt jsonb NOT NULL,
    response_text text NOT NULL DEFAULT '',
    response_meta jsonb NOT NULL DEFAULT '{}',
    result jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','sending','completed','failed','cancelled','uncertain')),
    cancel_requested boolean NOT NULL DEFAULT false,
    job_id uuid NOT NULL REFERENCES jobs(id),
    usage jsonb,
    reserved_usd numeric(20,8),
    cost_usd numeric(20,8),
    error text,
    sent_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,request_id),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id)
);
CREATE INDEX ai_calls_page ON ai_calls(project_id,ordinal DESC);
CREATE INDEX ai_calls_provider_budget ON ai_calls(provider_id,created_at);
ALTER TABLE ai_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_calls FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON ai_calls
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));

-- Provider-wide reservation ledger has no prompts or credentials. Jobs already
-- have a deployment-wide claim boundary; this ledger serializes shared quotas.
CREATE TABLE ai_reservations (
    -- Retain an accounting tombstone when an archived run is explicitly deleted.
    call_id uuid PRIMARY KEY,
    provider_id uuid NOT NULL REFERENCES ai_providers(id),
    active boolean NOT NULL DEFAULT true,
    reserved_usd numeric(20,8),
    cost_usd numeric(20,8),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_reservations_budget ON ai_reservations(provider_id,created_at);
INSERT INTO schema_version(version) VALUES(18);
