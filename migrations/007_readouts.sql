CREATE INDEX IF NOT EXISTS events_readout_page ON tm2.events(run_id,id DESC)
    WHERE kind IN ('structural_readout','temporal_readout');
INSERT INTO tm2.schema_version(version) VALUES (7);
