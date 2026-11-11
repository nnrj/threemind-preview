CREATE INDEX IF NOT EXISTS events_telemetry_page ON tm2.events(run_id,id DESC)
    WHERE kind='telemetry_sample';
INSERT INTO tm2.schema_version(version) VALUES (6);
