SET search_path TO tm2,pg_catalog;
CREATE INDEX input_frames_observation_labels ON input_frames(run_id,delivered_revision DESC,envelope_id,frame_index DESC)
    WHERE status='delivered' AND labels<>'{}'::jsonb;
CREATE INDEX input_frames_label_keys ON input_frames USING gin(labels)
    WHERE status='delivered' AND labels<>'{}'::jsonb;
INSERT INTO schema_version(version) VALUES(20);
