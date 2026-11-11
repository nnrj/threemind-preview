SET search_path TO tm2,pg_catalog;

-- Application authority is independent of PostgreSQL roles and Core.
CREATE TABLE platform_roles (
    id uuid PRIMARY KEY, key text NOT NULL UNIQUE, name text NOT NULL,
    builtin boolean NOT NULL DEFAULT false, revision bigint NOT NULL DEFAULT 1,
    permissions jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(permissions)='array'),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE platform_user_roles (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id uuid NOT NULL REFERENCES platform_roles(id) ON DELETE RESTRICT,
    PRIMARY KEY(user_id,role_id)
);
ALTER TABLE sessions ADD COLUMN remembered boolean NOT NULL DEFAULT false;
ALTER TABLE sessions ADD COLUMN source text NOT NULL DEFAULT 'human' CHECK(source IN ('human','ai','script'));
CREATE TABLE platform_delegations (
    id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
    token_hash text NOT NULL UNIQUE, name text NOT NULL,
    source text NOT NULL CHECK(source IN ('ai','script')),
    actions jsonb NOT NULL CHECK(jsonb_typeof(actions)='array'),
    resources jsonb NOT NULL CHECK(jsonb_typeof(resources)='array'),
    expires_at timestamptz NOT NULL, revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX platform_delegations_user ON platform_delegations(user_id,created_at);
INSERT INTO platform_roles(id,key,name,builtin,permissions) VALUES
('00000000-0000-4000-8000-000000000101','superadmin','超级管理员',true,'[]'),
('00000000-0000-4000-8000-000000000102','admin','管理员',true,'[{"action":"system.read","scope":"platform"},{"action":"services.read","scope":"platform"},{"action":"services.use","scope":"member_projects"},{"action":"projects.read","scope":"member_projects"},{"action":"projects.create","scope":"platform"},{"action":"projects.manage","scope":"member_projects"},{"action":"research.read","scope":"member_projects"},{"action":"research.write","scope":"member_projects"},{"action":"research.manage","scope":"member_projects"},{"action":"runs.read","scope":"member_projects"},{"action":"runs.create","scope":"member_projects"},{"action":"runs.control","scope":"member_projects"},{"action":"runs.configure","scope":"member_projects"},{"action":"experiments.read","scope":"member_projects"},{"action":"experiments.create","scope":"member_projects"},{"action":"experiments.control","scope":"member_projects"},{"action":"worlds.read","scope":"member_projects"},{"action":"worlds.write","scope":"member_projects"},{"action":"worlds.use","scope":"member_projects"},{"action":"data.read","scope":"member_projects"},{"action":"data.export","scope":"member_projects"},{"action":"data.import","scope":"member_projects"},{"action":"data.delete","scope":"member_projects"},{"action":"data.manage","scope":"member_projects"},{"action":"notes.read","scope":"own"},{"action":"notes.write","scope":"own"},{"action":"notes.delete","scope":"own"},{"action":"reports.read","scope":"member_projects"},{"action":"reports.write","scope":"member_projects"},{"action":"reports.export","scope":"member_projects"},{"action":"reports.share","scope":"member_projects"},{"action":"tools.read","scope":"member_projects"},{"action":"tools.use","scope":"member_projects"},{"action":"menu.overview","scope":"platform"},{"action":"menu.kernels","scope":"platform"},{"action":"menu.experiments","scope":"platform"},{"action":"menu.worlds","scope":"platform"},{"action":"menu.conversation","scope":"platform"},{"action":"menu.comparisons","scope":"platform"},{"action":"menu.query","scope":"platform"},{"action":"menu.models","scope":"platform"},{"action":"menu.notes","scope":"platform"},{"action":"menu.reports","scope":"platform"},{"action":"menu.data","scope":"platform"},{"action":"menu.settings","scope":"platform"},{"action":"menu.docs","scope":"platform"},{"action":"system.write","scope":"platform"},{"action":"accounts.read","scope":"platform"},{"action":"accounts.manage","scope":"platform"},{"action":"roles.read","scope":"platform"},{"action":"roles.manage","scope":"platform"},{"action":"services.manage","scope":"platform"},{"action":"menu.accounts","scope":"platform"},{"action":"runs.pause","scope":"member_projects"},{"action":"runs.resume","scope":"member_projects"},{"action":"runs.stimulate","scope":"member_projects"},{"action":"runs.intervene","scope":"member_projects"},{"action":"runs.checkpoint","scope":"member_projects"},{"action":"runs.restore","scope":"member_projects"},{"action":"runs.export","scope":"member_projects"},{"action":"runs.observe","scope":"member_projects"}]'),
('00000000-0000-4000-8000-000000000103','user','普通用户',true,'[{"action":"system.read","scope":"platform"},{"action":"services.read","scope":"platform"},{"action":"services.use","scope":"member_projects"},{"action":"projects.read","scope":"member_projects"},{"action":"projects.create","scope":"platform"},{"action":"projects.manage","scope":"member_projects"},{"action":"research.read","scope":"member_projects"},{"action":"research.write","scope":"member_projects"},{"action":"research.manage","scope":"member_projects"},{"action":"runs.read","scope":"member_projects"},{"action":"runs.create","scope":"member_projects"},{"action":"runs.control","scope":"member_projects"},{"action":"runs.configure","scope":"member_projects"},{"action":"experiments.read","scope":"member_projects"},{"action":"experiments.create","scope":"member_projects"},{"action":"experiments.control","scope":"member_projects"},{"action":"worlds.read","scope":"member_projects"},{"action":"worlds.write","scope":"member_projects"},{"action":"worlds.use","scope":"member_projects"},{"action":"data.read","scope":"member_projects"},{"action":"data.export","scope":"member_projects"},{"action":"data.import","scope":"member_projects"},{"action":"data.delete","scope":"member_projects"},{"action":"data.manage","scope":"member_projects"},{"action":"notes.read","scope":"own"},{"action":"notes.write","scope":"own"},{"action":"notes.delete","scope":"own"},{"action":"reports.read","scope":"member_projects"},{"action":"reports.write","scope":"member_projects"},{"action":"reports.export","scope":"member_projects"},{"action":"reports.share","scope":"member_projects"},{"action":"tools.read","scope":"member_projects"},{"action":"tools.use","scope":"member_projects"},{"action":"menu.overview","scope":"platform"},{"action":"menu.kernels","scope":"platform"},{"action":"menu.experiments","scope":"platform"},{"action":"menu.worlds","scope":"platform"},{"action":"menu.conversation","scope":"platform"},{"action":"menu.comparisons","scope":"platform"},{"action":"menu.query","scope":"platform"},{"action":"menu.models","scope":"platform"},{"action":"menu.notes","scope":"platform"},{"action":"menu.reports","scope":"platform"},{"action":"menu.data","scope":"platform"},{"action":"menu.settings","scope":"platform"},{"action":"menu.docs","scope":"platform"},{"action":"runs.pause","scope":"member_projects"},{"action":"runs.resume","scope":"member_projects"},{"action":"runs.stimulate","scope":"member_projects"},{"action":"runs.intervene","scope":"member_projects"},{"action":"runs.checkpoint","scope":"member_projects"},{"action":"runs.restore","scope":"member_projects"},{"action":"runs.export","scope":"member_projects"},{"action":"runs.observe","scope":"member_projects"}]');
-- Preserve established identity and all original authorship references.
UPDATE platform_roles SET permissions=permissions || '[{"action":"services.read","scope":"member_projects"},{"action":"tools.read","scope":"platform"}]'::jsonb WHERE key IN ('admin','user');
UPDATE platform_roles SET permissions=permissions || '[{"action":"menu.workbench","scope":"platform"},{"action":"menu.projects","scope":"platform"}]'::jsonb WHERE key IN ('admin','user');
UPDATE platform_roles SET permissions=permissions || '[{"action":"data.read","scope":"platform"},{"action":"data.manage","scope":"platform"}]'::jsonb WHERE key='admin';
INSERT INTO users(id,username,admin) VALUES('00000000-0000-4000-8000-000000000001','local',true)
ON CONFLICT(id) DO NOTHING;
INSERT INTO platform_user_roles(user_id,role_id)
SELECT id,CASE WHEN id='00000000-0000-4000-8000-000000000001' THEN '00000000-0000-4000-8000-000000000101'::uuid
    WHEN admin THEN '00000000-0000-4000-8000-000000000102'::uuid
    ELSE '00000000-0000-4000-8000-000000000103'::uuid END FROM users;

-- Transaction-local host authentication flags do not bypass immutable evidence
-- triggers. A selected project still limits lists, including superadmin lists.
DO $$ DECLARE relation text; boundary text; global_read text; private_table boolean; metadata_guard text; original_metadata text; BEGIN
    FOR relation IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='tm2' AND c.relkind='r' AND c.relrowsecurity LOOP
        IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='tm2' AND table_name=relation AND column_name='project_id') THEN
            boundary := '(nullif(current_setting(''tm.project_id'',true),'''') IS NULL OR project_id=nullif(current_setting(''tm.project_id'',true),'''')::uuid)';
            global_read := '(nullif(current_setting(''tm.permission_projects'',true),'''') IS NULL OR project_id::text=ANY(string_to_array(current_setting(''tm.permission_projects'',true),'','')))';
        ELSIF relation='projects' THEN
            boundary := '(nullif(current_setting(''tm.project_id'',true),'''') IS NULL OR id=nullif(current_setting(''tm.project_id'',true),'''')::uuid)';
            global_read := '(nullif(current_setting(''tm.permission_projects'',true),'''') IS NULL OR id::text=ANY(string_to_array(current_setting(''tm.permission_projects'',true),'','')))';
        ELSE
            boundary := 'true'; global_read := 'true';
        END IF;
        EXECUTE format('CREATE POLICY platform_superadmin ON tm2.%I USING(current_setting(''tm.platform_superadmin'',true)=''true'' AND %s) WITH CHECK(current_setting(''tm.platform_superadmin'',true)=''true'' AND %s)',relation,boundary,boundary);
        private_table := relation LIKE 'note%' OR relation IN ('data_bundles','data_bundle_chunks','data_private_carriers','research_record_private_counts');
        -- Whole-data export/read can see explicitly authorized private carriers.
        -- Research-wide scope alone never confers author-private note authority.
        IF relation LIKE 'note%' THEN
            global_read := global_read || ' AND current_setting(''tm.permission_domain'',true) IN (''notes'',''data'')';
        ELSIF private_table THEN
            global_read := global_read || ' AND current_setting(''tm.permission_domain'',true)=''data''';
        ELSE
            global_read := global_read || ' AND current_setting(''tm.permission_domain'',true) IN (''projects'',''research'',''runs'',''experiments'',''worlds'',''reports'',''data'')';
        END IF;
        IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='tm2' AND table_name=relation AND column_name='private_actor_id') THEN
            global_read := global_read || ' AND (current_setting(''tm.permission_domain'',true)=''data'' OR private_actor_id IS NULL OR private_actor_id::text=current_setting(''tm.permission_actor_id'',true))';
        END IF;
        metadata_guard := format('(coalesce(current_setting(''tm.permission_metadata_only'',true),''false'')<>''true'' OR %L=ANY(string_to_array(current_setting(''tm.permission_metadata_tables'',true),'','')))',relation);
        global_read := global_read || ' AND ' || metadata_guard;
        SELECT pg_get_expr(p.polqual,p.polrelid) INTO original_metadata FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='tm2' AND c.relname=relation AND p.polname='authorized_metadata_read';
        IF original_metadata IS NOT NULL THEN
            EXECUTE format('ALTER POLICY authorized_metadata_read ON tm2.%I USING ((%s) AND %s)',relation,original_metadata,metadata_guard);
        END IF;
        IF relation NOT IN ('runs','studies','research_experiments','research_documents','world_documents','world_versions',
            'evolution_campaigns','ecology_campaigns','assessment_batches','development_sessions','innate_versions',
            'language_sessions','species_assets','artifacts','experiment_bundles','data_bundles','media_assets',
            'probe_calibrations','report_sources','report_source_requests','notes','note_collections','projects','members') THEN
            global_read := global_read || ' AND current_setting(''tm.permission_metadata_only'',true)<>''true''';
        END IF;
        EXECUTE format('CREATE POLICY platform_scope_read ON tm2.%I FOR SELECT USING(current_setting(''tm.permission_all_projects'',true)=''true'' AND %s AND %s)',relation,boundary,global_read);
        EXECUTE format('CREATE POLICY platform_scope_write ON tm2.%I USING(current_setting(''tm.permission_all_projects'',true)=''true'' AND current_setting(''tm.permission_mutation'',true)=''true'' AND %s AND %s) WITH CHECK(current_setting(''tm.permission_all_projects'',true)=''true'' AND current_setting(''tm.permission_mutation'',true)=''true'' AND %s AND %s)',relation,boundary,global_read,boundary,global_read);
        IF relation LIKE 'note%' THEN
            EXECUTE format('CREATE POLICY platform_scoped_notes ON tm2.%I USING(current_setting(''tm.permission_private_notes'',true)=''true'' AND %s AND EXISTS(SELECT 1 FROM tm2.members m WHERE m.project_id=%I.project_id AND m.user_id=nullif(current_setting(''tm.permission_actor_id'',true),'''')::uuid)) WITH CHECK(current_setting(''tm.permission_private_notes'',true)=''true'' AND %s AND EXISTS(SELECT 1 FROM tm2.members m WHERE m.project_id=%I.project_id AND m.user_id=nullif(current_setting(''tm.permission_actor_id'',true),'''')::uuid))',relation,boundary,relation,boundary,relation);
        END IF;
    END LOOP;
END $$;
INSERT INTO schema_version(version) VALUES(66);
