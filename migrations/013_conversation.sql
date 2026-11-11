SET search_path = tm2, pg_catalog;
-- An observer index: pointers only, never a second scientific record or model state.
ALTER TABLE input_envelopes ADD CONSTRAINT input_envelopes_scope UNIQUE(project_id,run_id,id);
ALTER TABLE events ADD CONSTRAINT events_scope UNIQUE(project_id,run_id,id);
CREATE TABLE conversation_entries (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id uuid NOT NULL, run_id uuid NOT NULL,
    kind text NOT NULL CHECK(kind IN ('input','structural_readout','temporal_readout')),
    input_id uuid, event_id bigint, source text NOT NULL, envelope_key text,
    source_class text GENERATED ALWAYS AS (CASE
        WHEN source LIKE 'manual-%' OR source LIKE 'upload-%' OR source IN ('replay','text-sensor','anonymous-frames') THEN 'manual'
        WHEN source LIKE 'ai-%' THEN 'ai' ELSE 'environment' END) STORED,
    reconstructed boolean NOT NULL DEFAULT false,
    indexed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(input_id), UNIQUE(event_id),
    CHECK ((kind='input' AND input_id IS NOT NULL AND event_id IS NULL)
        OR (kind<>'input' AND input_id IS NULL AND event_id IS NOT NULL)),
    FOREIGN KEY(project_id,run_id) REFERENCES runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id,input_id) REFERENCES input_envelopes(project_id,run_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id,event_id) REFERENCES events(project_id,run_id,id) ON DELETE CASCADE
);
CREATE INDEX conversation_page ON conversation_entries(run_id,id DESC);
CREATE INDEX conversation_link ON conversation_entries(run_id,envelope_key,id) WHERE kind='temporal_readout';
-- Existing database rows need no Python/JSON scan or data-directory migration.
-- Their relative receipt order is reconstructed from wall-clock commits, explicitly marked.
DO $$ DECLARE p uuid; BEGIN
    FOR p IN SELECT id FROM projects LOOP
        PERFORM set_config('tm.project_id',p::text,true);
        INSERT INTO conversation_entries(project_id,run_id,kind,input_id,event_id,source,envelope_key,reconstructed)
        SELECT project_id,run_id,kind,input_id,event_id,source,envelope_key,true FROM (
            SELECT project_id,run_id,'input'::text AS kind,id AS input_id,NULL::bigint AS event_id,
                source,NULL::text AS envelope_key,created_at AS occurred_at,0 AS tie,ordinal AS ordering
                FROM input_envelopes WHERE project_id=p
            UNION ALL
            SELECT e.project_id,e.run_id,e.kind,NULL::uuid,e.id,COALESCE(e.payload->>'source',''),
                CASE WHEN e.kind='temporal_readout' THEN left(e.payload->>'envelope_id',128) END,
                COALESCE(c.created_at,r.created_at),1,e.id
                FROM events e JOIN runs r ON r.id=e.run_id
                LEFT JOIN checkpoints c ON c.run_id=e.run_id AND c.revision=e.commit_revision
                WHERE e.project_id=p AND e.kind IN ('structural_readout','temporal_readout')
        ) records ORDER BY run_id,occurred_at,tie,ordering;
    END LOOP;
    PERFORM set_config('tm.project_id','',true);
END $$;
ALTER TABLE conversation_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_entries FORCE ROW LEVEL SECURITY;
CREATE POLICY project_boundary ON conversation_entries
    USING(project_id::text=current_setting('tm.project_id',true)) WITH CHECK(project_id::text=current_setting('tm.project_id',true));
CREATE FUNCTION index_conversation_input() RETURNS trigger LANGUAGE plpgsql SET search_path=tm2,pg_catalog AS $$ BEGIN
    INSERT INTO conversation_entries(project_id,run_id,kind,input_id,source)
        VALUES(NEW.project_id,NEW.run_id,'input',NEW.id,NEW.source);
    RETURN NEW;
END $$;
CREATE FUNCTION index_conversation_readout() RETURNS trigger LANGUAGE plpgsql SET search_path=tm2,pg_catalog AS $$ BEGIN
    -- Worker commits readout events before persisting the environment input receipts.
    -- Deferral places those receipts first without changing execution/commit semantics.
    INSERT INTO conversation_entries(project_id,run_id,kind,event_id,source,envelope_key)
        VALUES(NEW.project_id,NEW.run_id,NEW.kind,NEW.id,COALESCE(NEW.payload->>'source',''),
            CASE WHEN NEW.kind='temporal_readout' THEN left(NEW.payload->>'envelope_id',128) END);
    RETURN NEW;
END $$;
CREATE TRIGGER conversation_input AFTER INSERT ON input_envelopes FOR EACH ROW EXECUTE FUNCTION index_conversation_input();
CREATE CONSTRAINT TRIGGER conversation_readout AFTER INSERT ON events DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW WHEN (NEW.kind IN ('structural_readout','temporal_readout')) EXECUTE FUNCTION index_conversation_readout();
INSERT INTO schema_version(version) VALUES(13);
