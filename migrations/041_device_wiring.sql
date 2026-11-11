SET search_path = tm2, pg_catalog;

-- Preserve every existing anonymous mapping; do not recreate device identities.
ALTER TABLE device_bindings ADD COLUMN wiring_id uuid;
ALTER TABLE device_bindings DISABLE ROW LEVEL SECURITY;
UPDATE device_bindings SET wiring_id=id;
ALTER TABLE device_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_bindings ALTER COLUMN wiring_id SET NOT NULL;
ALTER TABLE device_bindings ADD CONSTRAINT device_wiring_unique UNIQUE(run_id,wiring_id);

CREATE FUNCTION preserve_device_wiring() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.wiring_id IS DISTINCT FROM OLD.wiring_id THEN
        RAISE EXCEPTION 'device wiring is immutable; create an explicit new port'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER device_wiring_immutable BEFORE UPDATE OF wiring_id ON device_bindings
FOR EACH ROW EXECUTE FUNCTION preserve_device_wiring();
INSERT INTO schema_version(version) VALUES(41);
