SET search_path = tm2, pg_catalog;
ALTER TABLE conversation_entries DROP CONSTRAINT conversation_entries_kind_check;
ALTER TABLE conversation_entries ADD CONSTRAINT conversation_entries_kind_check
    CHECK(kind IN ('input','structural_readout','temporal_readout','external_interpretation'));
DROP TRIGGER conversation_readout ON events;
CREATE CONSTRAINT TRIGGER conversation_readout AFTER INSERT ON events DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW WHEN (NEW.kind IN ('structural_readout','temporal_readout','external_interpretation'))
    EXECUTE FUNCTION index_conversation_readout();
INSERT INTO schema_version(version) VALUES(48);
