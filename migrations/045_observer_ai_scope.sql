SET search_path TO tm2,pg_catalog;
ALTER TABLE ecology_ai_sources DROP CONSTRAINT ecology_ai_sources_call_id_fkey;
ALTER TABLE ecology_ai_sources ADD CONSTRAINT ecology_ai_call_project
    FOREIGN KEY(project_id,call_id) REFERENCES ai_calls(project_id,id);
INSERT INTO schema_version(version) VALUES(45);
