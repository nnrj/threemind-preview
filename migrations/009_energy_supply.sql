SET search_path = tm2, pg_catalog;
-- A resource command can be retried after response loss without supplying twice.
CREATE UNIQUE INDEX energy_supply_request ON commands(run_id, (payload->>'request_id'))
    WHERE kind='energy_supply';
INSERT INTO schema_version(version) VALUES(9);
