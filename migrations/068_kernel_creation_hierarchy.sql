SET search_path TO tm2,pg_catalog;

-- Host metadata only. Historical choices are not fabricated or model states rewritten.
ALTER TABLE runs ADD COLUMN execution jsonb NOT NULL DEFAULT '{}';
ALTER TABLE creation_templates ADD COLUMN source jsonb NOT NULL DEFAULT '{}';
ALTER TABLE creation_template_versions ADD COLUMN source jsonb NOT NULL DEFAULT '{}';

-- The original frame runtime has string node identities and 64-bit receptor
-- channels. Its read projection is separate from causal's integer row schema.
CREATE TABLE legacy_graph_rows (
    project_id uuid NOT NULL REFERENCES projects(id),
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    kind text NOT NULL CHECK(kind IN ('nodes','edges')),
    identity text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY(run_id,kind,identity)
);
ALTER TABLE legacy_graph_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE legacy_graph_rows FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON legacy_graph_rows
    USING(project_id::text=current_setting('tm.project_id',true))
    WITH CHECK(project_id::text=current_setting('tm.project_id',true));

ALTER FUNCTION required_job_features(text,uuid,jsonb) RENAME TO required_job_features_v67;
CREATE FUNCTION required_job_features(task_kind text,task_run uuid,task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
DECLARE features text[]; identity text; backend text;
BEGIN
    features := required_job_features_v67(task_kind,task_run,task_params);
    IF task_run IS NOT NULL THEN
        SELECT spec->>'kernel_id', execution->>'backend' INTO identity,backend FROM runs WHERE id=task_run;
    ELSIF task_kind='study' THEN
        identity := task_params#>>'{protocol,base,kernel_id}';
    ELSIF task_kind='ecology' THEN
        SELECT protocol#>>'{base,kernel_id}' INTO identity FROM ecology_campaigns WHERE id=(task_params->>'campaign_id')::uuid;
    END IF;
    IF task_kind IN ('run','study','analysis','probe_calibration','ecology','assessment') AND identity IS NOT NULL THEN
        backend := coalesce(backend,task_params#>>'{execution,backend}');
        IF identity='unified-associative' THEN backend := coalesce(backend,'reference'); END IF;
        IF backend IS NOT NULL OR identity IN ('threemind.causal/1','threemind.causal/2','threemind.causal/3',
            'threemind.causal/4','threemind.causal/5','threemind.causal/6','threemind.causal/7','threemind.causal/8','unified-associative') THEN
            features := array_append(features,'worker.kernel_'||replace(replace(identity,'threemind.',''),'/',''));
        END IF;
        IF backend IS NOT NULL THEN features := array_append(features,'worker.backend:'||backend); END IF;
    END IF;
    RETURN ARRAY(SELECT feature FROM unnest(features) WITH ORDINALITY AS f(feature,position)
                 GROUP BY feature ORDER BY min(position));
END $$;

-- Public system defaults do not grant visibility into other projects' host jobs.
-- Preserve role revisions and grant the new monitor capability only to admins.
UPDATE platform_roles SET
    permissions=permissions || '[{"action":"execution.read","scope":"platform"}]'::jsonb,
    revision=revision+1
WHERE key='admin' AND NOT permissions @> '[{"action":"execution.read","scope":"platform"}]'::jsonb;

INSERT INTO schema_version(version) VALUES(68);
