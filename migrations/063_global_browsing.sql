SET search_path TO tm2,pg_catalog;

-- Only metadata supports the authenticated cross-project SELECT context.
-- Existing project write policies and raw trajectories/checkpoints are unchanged.
DO $$ DECLARE relation text; boundary text; BEGIN
    FOREACH relation IN ARRAY ARRAY[
        'runs','studies','research_documents','research_document_versions',
        'world_documents','world_versions','evolution_campaigns','ecology_campaigns',
        'assessment_batches','development_sessions','innate_versions','language_sessions',
        'species_assets','report_sources','report_source_requests','probe_calibrations',
        'media_assets','jobs','notes','note_collections','artifacts','experiment_bundles',
        'data_bundles','data_private_carriers'
    ] LOOP
        boundary := 'project_id IN (SELECT m.project_id FROM tm2.members m JOIN tm2.users u ON u.id=m.user_id '
            || 'WHERE m.user_id::text=current_setting(''tm.browse_user_id'',true) AND u.enabled)';
        IF relation IN ('notes','note_collections') THEN
            boundary := boundary || ' AND owner_id::text=current_setting(''tm.browse_user_id'',true)';
        ELSIF relation IN ('experiment_bundles','data_bundles') THEN
            boundary := boundary || ' AND (NOT private OR actor_id::text=current_setting(''tm.browse_user_id'',true))';
        ELSIF relation='artifacts' THEN
            boundary := boundary || ' AND tm2.private_data_carrier_visible(''artifact'',id) '
                || 'AND (coalesce(metadata->>''private'',''false'')<>''true'' '
                || 'OR metadata->>''private_actor_id''=current_setting(''tm.browse_user_id'',true))';
        END IF;
        EXECUTE format('CREATE POLICY authorized_metadata_read ON tm2.%I FOR SELECT USING (%s)',relation,boundary);
    END LOOP;
END $$;
INSERT INTO schema_version(version) VALUES(63);
