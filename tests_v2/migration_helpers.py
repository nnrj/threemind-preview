def remove_observer_schema(db):
    """Reconstruct a pre-42 boundary in a disposable migration fixture only."""
    assert db.info.dbname.startswith("tm2_test_db_")
    if db.execute("SELECT 1 FROM tm2.schema_version WHERE version=54").fetchone():
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v53(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version=54")
    if db.execute("SELECT 1 FROM tm2.schema_version WHERE version=53").fetchone():
        db.execute("DROP TABLE tm2.bundle_resumes,tm2.experiment_bundles,tm2.bundle_upload_chunks,tm2.bundle_uploads")
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v52(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version=53")
    if db.execute("SELECT 1 FROM tm2.schema_version WHERE version=52").fetchone():
        db.execute("DROP TABLE tm2.operation_receipts")
        db.execute("DELETE FROM tm2.schema_version WHERE version=52")
    if db.execute("SELECT 1 FROM tm2.schema_version WHERE version=51").fetchone():
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v50(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version=51")
    if db.execute("SELECT 1 FROM tm2.schema_version WHERE version=50").fetchone():
        db.execute("ALTER TABLE tm2.report_source_requests DROP COLUMN calibration_id")
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v49(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version=50")
    if db.execute("SELECT 1 FROM tm2.schema_version WHERE version=49").fetchone():
        db.execute("DROP TABLE tm2.probe_calibrations")
        db.execute("DROP FUNCTION tm2.preserve_probe_calibration()")
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v48(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version=49")
    # Reconstruct a genuine historical schema; deleting version rows alone
    # would leave new columns behind and is not an upgrade test.
    if db.execute("SELECT 1 FROM tm2.schema_version WHERE version=48").fetchone():
        db.execute("ALTER TABLE tm2.conversation_entries DROP CONSTRAINT conversation_entries_kind_check")
        db.execute(
            "ALTER TABLE tm2.conversation_entries ADD CHECK(kind IN ('input','structural_readout','temporal_readout'))"
        )
        db.execute("DROP TRIGGER conversation_readout ON tm2.events")
        db.execute(
            "CREATE CONSTRAINT TRIGGER conversation_readout AFTER INSERT ON tm2.events DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.kind IN ('structural_readout','temporal_readout')) EXECUTE FUNCTION tm2.index_conversation_readout()"
        )
        db.execute("DELETE FROM tm2.schema_version WHERE version=48")
    if db.execute("SELECT 1 FROM tm2.schema_version WHERE version=47").fetchone():
        db.execute(
            "ALTER TABLE tm2.nodes DROP COLUMN birth_us,DROP COLUMN local_plasticity,DROP COLUMN pending_inhibition,DROP COLUMN generated_inhibition"
        )
        db.execute("DELETE FROM tm2.schema_version WHERE version=47")
    if db.execute("SELECT to_regclass('tm2.execution_health_monitors')").fetchone()[0] is not None:
        db.execute("DROP TABLE tm2.execution_health_monitors")
        db.execute("ALTER TABLE tm2.workers DROP COLUMN health,DROP COLUMN health_received_at")
        db.execute("DROP TRIGGER timestamp_job_status ON tm2.jobs")
        db.execute("DROP FUNCTION tm2.timestamp_job_status()")
        db.execute("ALTER TABLE tm2.jobs DROP COLUMN status_changed_at")
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v45(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DROP TRIGGER notification_job_finished ON tm2.jobs")
        db.execute(
            "CREATE TRIGGER notification_job_finished AFTER UPDATE OF status ON tm2.jobs FOR EACH ROW "
            "WHEN (OLD.status IS DISTINCT FROM NEW.status AND NEW.status IN ('done','failed') "
            "AND NEW.kind IN ('export','data_export','analysis')) EXECUTE FUNCTION tm2.notify_job_finished()"
        )
        db.execute("DELETE FROM tm2.schema_version WHERE version=46")
    if db.execute("SELECT to_regclass('tm2.ecology_ai_schedules')").fetchone()[0] is not None:
        db.execute("DROP TABLE tm2.ecology_ai_sources,tm2.ecology_ai_schedules,tm2.ecology_ai_revisions")
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v43(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version IN (44,45)")
    if db.execute("SELECT to_regclass('tm2.assessment_batches')").fetchone()[0] is not None:
        db.execute("ALTER TABLE tm2.report_source_requests DROP COLUMN assessment_id")
        db.execute("DROP TABLE tm2.assessment_actions,tm2.assessment_members,tm2.assessment_batches")
        db.execute("DROP FUNCTION tm2.preserve_assessment()")
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v42(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version=43")
    db.execute("DROP TRIGGER wake_observers ON tm2.ecology_checkpoints")
    db.execute("DROP FUNCTION tm2.wake_ecology_observers()")
    db.execute("DROP INDEX tm2.ecology_observer_waiting_jobs")
    db.execute("DROP TABLE tm2.ecology_observer_entries,tm2.ecology_observers,tm2.ecology_observer_revisions")
    db.execute("ALTER TABLE tm2.jobs DROP COLUMN available_at")
    db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
    db.execute("ALTER FUNCTION tm2.required_job_features_v41(text,uuid,jsonb) RENAME TO required_job_features")
    db.execute("DELETE FROM tm2.schema_version WHERE version=42")
