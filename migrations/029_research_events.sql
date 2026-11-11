SET search_path TO tm2,pg_catalog;

ALTER TABLE report_source_requests DROP CONSTRAINT report_source_requests_kind_check;
ALTER TABLE report_source_requests ADD CHECK(kind IN ('trajectory','nodes','edges','analysis','events'));

-- The additional source kind needs matching renderers, exporters and AI validation.
-- Existing jobs retain their recorded requirements; all new document jobs use this release.
CREATE OR REPLACE FUNCTION required_job_features(task_kind text, task_run uuid, task_params jsonb) RETURNS text[]
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF task_kind='ai' AND task_params->>'purpose' IN ('record','report') THEN
        RETURN ARRAY['worker.ai','worker.research_ai_v1','worker.research_events_v1'];
    END IF;
    IF task_kind='report_export' THEN RETURN ARRAY['worker.report_export_v1','worker.research_events_v1']; END IF;
    IF task_kind='report_source' THEN RETURN ARRAY['worker.research_documents','worker.research_events_v1']; END IF;
    RETURN required_job_features_v24(task_kind,task_run,task_params);
END $$;
INSERT INTO schema_version(version) VALUES(29);
