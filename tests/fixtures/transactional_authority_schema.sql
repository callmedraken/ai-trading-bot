PRAGMA foreign_keys = ON;

CREATE TABLE authority_metadata (
    authority_epoch_id TEXT PRIMARY KEY,
    machine_authority_id TEXT NOT NULL UNIQUE,
    bootstrap_schema INTEGER NOT NULL CHECK (bootstrap_schema > 0),
    bootstrap_generation INTEGER NOT NULL CHECK (bootstrap_generation > 0),
    signing_key_id TEXT NOT NULL,
    approved_account_sid TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    permitted_provider_operation TEXT NOT NULL,
    authority_policy_version TEXT NOT NULL,
    claim_policy_version TEXT NOT NULL,
    created_at_utc TEXT NOT NULL CHECK (
        typeof(created_at_utc) = 'text'
        AND length(created_at_utc) = 20
        AND created_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(created_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(created_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(created_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(created_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', created_at_utc) IS created_at_utc
    ),
    bootstrap_digest BLOB NOT NULL CHECK (length(bootstrap_digest) = 32),
    database_identity_digest BLOB NOT NULL CHECK (length(database_identity_digest) = 32),
    metadata_json BLOB NOT NULL,
    metadata_digest BLOB NOT NULL CHECK (length(metadata_digest) = 32),
    singleton_key INTEGER NOT NULL UNIQUE CHECK (singleton_key = 1)
);

CREATE TABLE schema_migrations (
    migration_id TEXT PRIMARY KEY,
    authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata(authority_epoch_id),
    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
    migration_policy_version TEXT NOT NULL,
    migration_digest BLOB NOT NULL CHECK (length(migration_digest) = 32),
    application_release_digest BLOB NOT NULL CHECK (length(application_release_digest) = 32),
    migration_json BLOB NOT NULL,
    applied_at_utc TEXT NOT NULL CHECK (
        typeof(applied_at_utc) = 'text'
        AND length(applied_at_utc) = 20
        AND applied_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(applied_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(applied_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(applied_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(applied_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', applied_at_utc) IS applied_at_utc
    ),
    UNIQUE (authority_epoch_id, schema_version)
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata(authority_epoch_id),
    session_schema INTEGER NOT NULL CHECK (session_schema = 1),
    authority_policy_version TEXT NOT NULL,
    claim_policy_version TEXT NOT NULL,
    target_session_date TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('OPEN', 'SUCCESS_SELECTED', 'CLOSED')),
    next_attempt_ordinal INTEGER NOT NULL CHECK (next_attempt_ordinal >= 0),
    next_recovery_ordinal INTEGER NOT NULL CHECK (next_recovery_ordinal >= 0),
    request_json BLOB NOT NULL,
    request_digest BLOB NOT NULL CHECK (length(request_digest) = 32),
    created_at_utc TEXT NOT NULL CHECK (
        typeof(created_at_utc) = 'text'
        AND length(created_at_utc) = 20
        AND created_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(created_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(created_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(created_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(created_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', created_at_utc) IS created_at_utc
    ),
    closed_at_utc TEXT CHECK (
        closed_at_utc IS NULL OR (
            typeof(closed_at_utc) = 'text'
            AND length(closed_at_utc) = 20
            AND closed_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND substr(closed_at_utc, 1, 4) BETWEEN '0001' AND '9999'
            AND substr(closed_at_utc, 12, 2) BETWEEN '00' AND '23'
            AND substr(closed_at_utc, 15, 2) BETWEEN '00' AND '59'
            AND substr(closed_at_utc, 18, 2) BETWEEN '00' AND '59'
            AND strftime('%Y-%m-%dT%H:%M:%SZ', closed_at_utc) IS closed_at_utc
        )
    ),
    close_reason TEXT,
    CHECK (
        (state = 'CLOSED' AND closed_at_utc IS NOT NULL AND close_reason IS NOT NULL)
        OR (state <> 'CLOSED' AND closed_at_utc IS NULL AND close_reason IS NULL)
    )
);

CREATE TABLE attempts (
    attempt_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    provider_id TEXT NOT NULL,
    permitted_provider_operation TEXT NOT NULL,
    provider_call_budget INTEGER NOT NULL CHECK (provider_call_budget = 1),
    request_json BLOB NOT NULL,
    request_digest BLOB NOT NULL CHECK (length(request_digest) = 32),
    attempt_schema INTEGER NOT NULL CHECK (attempt_schema = 1),
    attempt_policy_version TEXT NOT NULL,
    allocation_evidence_json BLOB NOT NULL,
    allocation_evidence_digest BLOB NOT NULL CHECK (length(allocation_evidence_digest) = 32),
    attempt_evidence_json BLOB NOT NULL,
    attempt_evidence_digest BLOB NOT NULL CHECK (length(attempt_evidence_digest) = 32),
    state TEXT NOT NULL CHECK (state IN (
        'ALLOCATED', 'CLAIM_COMMITTED', 'LAUNCH_RESERVED',
        'LAUNCH_MAY_HAVE_OCCURRED', 'TERMINAL_RECORDED',
        'SUCCESS_SELECTED', 'CLOSED'
    )),
    created_at_utc TEXT NOT NULL CHECK (
        typeof(created_at_utc) = 'text'
        AND length(created_at_utc) = 20
        AND created_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(created_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(created_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(created_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(created_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', created_at_utc) IS created_at_utc
    ),
    UNIQUE (session_id, ordinal)
);

CREATE TABLE provider_call_claims (
    claim_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(attempt_id),
    claim_schema INTEGER NOT NULL CHECK (claim_schema = 1),
    claim_policy_version TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    permitted_provider_operation TEXT NOT NULL,
    provider_call_budget INTEGER NOT NULL CHECK (provider_call_budget = 1),
    request_json BLOB NOT NULL,
    request_digest BLOB NOT NULL CHECK (length(request_digest) = 32),
    claim_evidence_json BLOB NOT NULL,
    claim_evidence_digest BLOB NOT NULL CHECK (length(claim_evidence_digest) = 32),
    state TEXT NOT NULL CHECK (state = 'COMMITTED'),
    committed_at_utc TEXT NOT NULL CHECK (
        typeof(committed_at_utc) = 'text'
        AND length(committed_at_utc) = 20
        AND committed_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(committed_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(committed_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(committed_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(committed_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', committed_at_utc) IS committed_at_utc
    )
);

CREATE TABLE launch_reservations (
    launch_reservation_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL UNIQUE REFERENCES provider_call_claims(claim_id),
    launch_reservation_schema INTEGER NOT NULL CHECK (launch_reservation_schema = 1),
    application_release_version TEXT NOT NULL,
    authority_policy_version TEXT NOT NULL,
    claim_policy_version TEXT NOT NULL,
    request_digest BLOB NOT NULL CHECK (length(request_digest) = 32),
    reservation_evidence_json BLOB NOT NULL,
    reservation_evidence_digest BLOB NOT NULL CHECK (length(reservation_evidence_digest) = 32),
    process_intent_json BLOB,
    process_intent_digest BLOB,
    process_intent_committed_at_utc TEXT CHECK (
        process_intent_committed_at_utc IS NULL OR (
            typeof(process_intent_committed_at_utc) = 'text'
            AND length(process_intent_committed_at_utc) = 20
            AND process_intent_committed_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND substr(process_intent_committed_at_utc, 1, 4) BETWEEN '0001' AND '9999'
            AND substr(process_intent_committed_at_utc, 12, 2) BETWEEN '00' AND '23'
            AND substr(process_intent_committed_at_utc, 15, 2) BETWEEN '00' AND '59'
            AND substr(process_intent_committed_at_utc, 18, 2) BETWEEN '00' AND '59'
            AND strftime('%Y-%m-%dT%H:%M:%SZ', process_intent_committed_at_utc) IS process_intent_committed_at_utc
        )
    ),
    reservation_state TEXT NOT NULL CHECK (reservation_state IN (
        'COMMITTED', 'PROCESS_INTENT_COMMITTED', 'PROCESS_CREATED',
        'PROCESS_CREATION_FAILED', 'MANUAL_REVIEW', 'TERMINAL_RECORDED'
    )),
    process_creation_failure_json BLOB,
    process_creation_failure_digest BLOB,
    committed_at_utc TEXT NOT NULL CHECK (
        typeof(committed_at_utc) = 'text'
        AND length(committed_at_utc) = 20
        AND committed_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(committed_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(committed_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(committed_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(committed_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', committed_at_utc) IS committed_at_utc
    ),
    outcome_recorded_at_utc TEXT CHECK (
        outcome_recorded_at_utc IS NULL OR (
            typeof(outcome_recorded_at_utc) = 'text'
            AND length(outcome_recorded_at_utc) = 20
            AND outcome_recorded_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND substr(outcome_recorded_at_utc, 1, 4) BETWEEN '0001' AND '9999'
            AND substr(outcome_recorded_at_utc, 12, 2) BETWEEN '00' AND '23'
            AND substr(outcome_recorded_at_utc, 15, 2) BETWEEN '00' AND '59'
            AND substr(outcome_recorded_at_utc, 18, 2) BETWEEN '00' AND '59'
            AND strftime('%Y-%m-%dT%H:%M:%SZ', outcome_recorded_at_utc) IS outcome_recorded_at_utc
        )
    ),
    CHECK (
        (process_intent_json IS NULL)
        = (process_intent_digest IS NULL)
        AND (process_intent_json IS NULL)
        = (process_intent_committed_at_utc IS NULL)
    ),
    CHECK (process_intent_digest IS NULL OR length(process_intent_digest) = 32),
    CHECK ((process_creation_failure_json IS NULL) = (process_creation_failure_digest IS NULL)),
    CHECK (
        process_creation_failure_digest IS NULL
        OR length(process_creation_failure_digest) = 32
    )
);

CREATE TABLE launch_executions (
    launch_execution_id TEXT PRIMARY KEY,
    launch_reservation_id TEXT NOT NULL UNIQUE REFERENCES launch_reservations(launch_reservation_id),
    launch_schema INTEGER NOT NULL CHECK (launch_schema = 1),
    application_release_version TEXT NOT NULL,
    authority_policy_version TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN (
        'PRE_RESUME_READY', 'RESUME_INTENT_COMMITTED', 'RESUME_RECORDED',
        'POST_RESUME_AMBIGUOUS', 'TERMINAL_RECORDED', 'CLOSED'
    )),
    process_creation_json BLOB NOT NULL,
    process_creation_digest BLOB NOT NULL CHECK (length(process_creation_digest) = 32),
    job_object_json BLOB NOT NULL,
    job_object_digest BLOB NOT NULL CHECK (length(job_object_digest) = 32),
    resume_authorization_json BLOB NOT NULL,
    resume_authorization_digest BLOB NOT NULL CHECK (length(resume_authorization_digest) = 32),
    resume_intent_json BLOB,
    resume_intent_digest BLOB,
    resume_intent_committed_at_utc TEXT CHECK (
        resume_intent_committed_at_utc IS NULL OR (
            typeof(resume_intent_committed_at_utc) = 'text'
            AND length(resume_intent_committed_at_utc) = 20
            AND resume_intent_committed_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
            AND substr(resume_intent_committed_at_utc, 1, 4) BETWEEN '0001' AND '9999'
            AND substr(resume_intent_committed_at_utc, 12, 2) BETWEEN '00' AND '23'
            AND substr(resume_intent_committed_at_utc, 15, 2) BETWEEN '00' AND '59'
            AND substr(resume_intent_committed_at_utc, 18, 2) BETWEEN '00' AND '59'
            AND strftime('%Y-%m-%dT%H:%M:%SZ', resume_intent_committed_at_utc) IS resume_intent_committed_at_utc
        )
    ),
    post_resume_json BLOB,
    post_resume_digest BLOB,
    cleanup_json BLOB,
    cleanup_digest BLOB,
    created_at_utc TEXT NOT NULL CHECK (
        typeof(created_at_utc) = 'text'
        AND length(created_at_utc) = 20
        AND created_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(created_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(created_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(created_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(created_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', created_at_utc) IS created_at_utc
    ),
    CHECK (resume_intent_digest IS NULL OR length(resume_intent_digest) = 32),
    CHECK (post_resume_digest IS NULL OR length(post_resume_digest) = 32),
    CHECK (cleanup_digest IS NULL OR length(cleanup_digest) = 32),
    CHECK ((resume_intent_json IS NULL) = (resume_intent_digest IS NULL)),
    CHECK ((resume_intent_json IS NULL) = (resume_intent_committed_at_utc IS NULL)),
    CHECK ((post_resume_json IS NULL) = (post_resume_digest IS NULL)),
    CHECK ((cleanup_json IS NULL) = (cleanup_digest IS NULL))
);

CREATE TABLE terminals (
    terminal_id TEXT PRIMARY KEY,
    launch_reservation_id TEXT NOT NULL UNIQUE REFERENCES launch_reservations(launch_reservation_id),
    terminal_schema INTEGER NOT NULL CHECK (terminal_schema = 1),
    terminal_policy_version TEXT NOT NULL,
    terminal_state TEXT NOT NULL CHECK (terminal_state IN ('SUCCEEDED', 'FAILED', 'AMBIGUOUS', 'CLOSED')),
    provider_call_disposition TEXT NOT NULL CHECK (
        provider_call_disposition IN ('NOT_STARTED', 'CONFIRMED', 'MAY_HAVE_OCCURRED')
    ),
    request_digest BLOB NOT NULL CHECK (length(request_digest) = 32),
    evidence_json BLOB NOT NULL,
    evidence_digest BLOB NOT NULL CHECK (length(evidence_digest) = 32),
    snapshot_digest BLOB,
    sanitized_diagnostics_json BLOB NOT NULL,
    sanitized_diagnostics_digest BLOB NOT NULL CHECK (length(sanitized_diagnostics_digest) = 32),
    recorded_at_utc TEXT NOT NULL CHECK (
        typeof(recorded_at_utc) = 'text'
        AND length(recorded_at_utc) = 20
        AND recorded_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(recorded_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(recorded_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(recorded_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(recorded_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', recorded_at_utc) IS recorded_at_utc
    ),
    CHECK (snapshot_digest IS NULL OR length(snapshot_digest) = 32)
);

CREATE TABLE session_selections (
    selection_id TEXT NOT NULL UNIQUE,
    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id),
    terminal_id TEXT NOT NULL UNIQUE REFERENCES terminals(terminal_id),
    selection_schema INTEGER NOT NULL CHECK (selection_schema = 1),
    selection_policy_version TEXT NOT NULL,
    snapshot_digest BLOB NOT NULL CHECK (length(snapshot_digest) = 32),
    selection_evidence_json BLOB NOT NULL,
    selection_evidence_digest BLOB NOT NULL CHECK (length(selection_evidence_digest) = 32),
    selected_at_utc TEXT NOT NULL CHECK (
        typeof(selected_at_utc) = 'text'
        AND length(selected_at_utc) = 20
        AND selected_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(selected_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(selected_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(selected_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(selected_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', selected_at_utc) IS selected_at_utc
    )
);

CREATE TABLE manual_recoveries (
    recovery_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    recovery_ordinal INTEGER NOT NULL CHECK (recovery_ordinal >= 0),
    target_kind TEXT NOT NULL CHECK (target_kind IN (
        'SESSION', 'ATTEMPT', 'CLAIM', 'LAUNCH_RESERVATION', 'TERMINAL'
    )),
    target_id TEXT NOT NULL CHECK (length(target_id) > 0),
    action TEXT NOT NULL CHECK (action IN (
        'RECORD_ATTEMPT_AMBIGUITY',
        'RECORD_CLAIM_AMBIGUITY',
        'CLASSIFY_LAUNCH_RESERVATION',
        'CLASSIFY_PROCESS_OUTCOME_UNKNOWN',
        'CLASSIFY_PRE_RESUME_READY',
        'CLASSIFY_RESUME_OUTCOME_UNKNOWN',
        'SELECT_COMMITTED_SUCCESS',
        'CLOSE_SESSION',
        'ACKNOWLEDGE_RESTORE'
    )),
    predecessor_state TEXT NOT NULL,
    resulting_state TEXT NOT NULL,
    recovery_schema INTEGER NOT NULL CHECK (recovery_schema = 1),
    recovery_policy_version TEXT NOT NULL,
    operator_evidence_json BLOB NOT NULL,
    operator_evidence_digest BLOB NOT NULL CHECK (length(operator_evidence_digest) = 32),
    created_at_utc TEXT NOT NULL CHECK (
        typeof(created_at_utc) = 'text'
        AND length(created_at_utc) = 20
        AND created_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'
        AND substr(created_at_utc, 1, 4) BETWEEN '0001' AND '9999'
        AND substr(created_at_utc, 12, 2) BETWEEN '00' AND '23'
        AND substr(created_at_utc, 15, 2) BETWEEN '00' AND '59'
        AND substr(created_at_utc, 18, 2) BETWEEN '00' AND '59'
        AND strftime('%Y-%m-%dT%H:%M:%SZ', created_at_utc) IS created_at_utc
    ),
    UNIQUE (session_id, recovery_ordinal)
);

CREATE TRIGGER authority_metadata_before_insert
BEFORE INSERT ON authority_metadata
FOR EACH ROW
BEGIN
    SELECT CASE WHEN sha256(NEW.metadata_json) IS NOT NEW.metadata_digest
        THEN RAISE(ABORT, 'authority metadata evidence digest is invalid') END;
END;

CREATE TRIGGER authority_metadata_no_update
BEFORE UPDATE ON authority_metadata
BEGIN
    SELECT RAISE(ABORT, 'authority metadata is immutable');
END;

CREATE TRIGGER authority_metadata_no_delete
BEFORE DELETE ON authority_metadata
BEGIN
    SELECT RAISE(ABORT, 'authority metadata cannot be deleted');
END;

CREATE TRIGGER schema_migrations_no_update
BEFORE UPDATE ON schema_migrations
BEGIN
    SELECT RAISE(ABORT, 'schema migrations are immutable');
END;

CREATE TRIGGER schema_migrations_before_insert
BEFORE INSERT ON schema_migrations
FOR EACH ROW
BEGIN
    SELECT CASE WHEN sha256(NEW.migration_json) IS NOT NEW.migration_digest
        THEN RAISE(ABORT, 'migration evidence digest is invalid') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM authority_metadata m
        WHERE m.authority_epoch_id = NEW.authority_epoch_id
          AND NEW.applied_at_utc >= m.created_at_utc
    ) THEN RAISE(ABORT, 'migration timestamp predates authority metadata') END;
END;

CREATE TRIGGER schema_migrations_no_delete
BEFORE DELETE ON schema_migrations
BEGIN
    SELECT RAISE(ABORT, 'schema migrations cannot be deleted');
END;

CREATE TRIGGER sessions_before_insert
BEFORE INSERT ON sessions
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT (
        NEW.state = 'OPEN'
        AND NEW.next_attempt_ordinal = 0
        AND NEW.next_recovery_ordinal = 0
        AND NEW.closed_at_utc IS NULL
        AND NEW.close_reason IS NULL
    ) THEN RAISE(ABORT, 'new sessions must start in the canonical open state') END;
    SELECT CASE WHEN typeof(NEW.request_json) <> 'blob'
        OR json_valid(NEW.request_json) <> 1
        THEN RAISE(ABORT, 'session request must be valid JSON BLOB bytes') END;
    SELECT CASE WHEN json_type(NEW.request_json) IS NOT 'object'
        THEN RAISE(ABORT, 'session request root must be an object') END;
    SELECT CASE WHEN (SELECT count(*) FROM json_each(NEW.request_json)) <> 10
        OR EXISTS (
            SELECT 1 FROM json_each(NEW.request_json)
            WHERE key NOT IN (
                'bar_interval',
                'child_operation_version',
                'ordered_universe',
                'output_policy_version',
                'permitted_provider_operation',
                'provider_id',
                'request_limit',
                'request_window_end_date',
                'request_window_start_date',
                'target_session_date'
            )
        )
        OR json_type(NEW.request_json, '$.bar_interval') IS NOT 'text'
        OR json_type(NEW.request_json, '$.child_operation_version') IS NOT 'text'
        OR json_type(NEW.request_json, '$.ordered_universe') IS NOT 'array'
        OR json_type(NEW.request_json, '$.output_policy_version') IS NOT 'text'
        OR json_type(NEW.request_json, '$.permitted_provider_operation') IS NOT 'text'
        OR json_type(NEW.request_json, '$.provider_id') IS NOT 'text'
        OR json_type(NEW.request_json, '$.request_limit') IS NOT 'integer'
        OR json_type(NEW.request_json, '$.request_window_end_date') IS NOT 'text'
        OR json_type(NEW.request_json, '$.request_window_start_date') IS NOT 'text'
        OR json_type(NEW.request_json, '$.target_session_date') IS NOT 'text'
        THEN RAISE(ABORT, 'session request fields or types are invalid') END;
    SELECT CASE WHEN json_extract(NEW.request_json, '$.bar_interval') IS NOT '1d'
        OR json_extract(NEW.request_json, '$.child_operation_version') IS NOT 'child/v1'
        OR json_extract(NEW.request_json, '$.output_policy_version') IS NOT 'output/v1'
        OR json_extract(NEW.request_json, '$.provider_id') IS NOT 'alpaca-market-data'
        OR json_extract(
            NEW.request_json,
            '$.permitted_provider_operation'
        ) IS NOT 'historical-stock-bars-v2-raw-usd-no-asof'
        THEN RAISE(ABORT, 'session request fixed semantics are invalid') END;
    SELECT CASE WHEN json_extract(NEW.request_json, '$.target_session_date')
            IS NOT NEW.target_session_date
        THEN RAISE(ABORT, 'session target date differs from request') END;
    SELECT CASE WHEN json_extract(NEW.request_json, '$.request_limit') NOT BETWEEN 1 AND 100
        OR json_array_length(NEW.request_json, '$.ordered_universe') NOT BETWEEN 1 AND 100
        OR json_extract(NEW.request_json, '$.request_limit')
            <> json_array_length(NEW.request_json, '$.ordered_universe')
        OR EXISTS (
            SELECT 1 FROM json_each(NEW.request_json, '$.ordered_universe')
            WHERE type <> 'text'
               OR length(value) NOT BETWEEN 1 AND 10
               OR value GLOB '*[^A-Z0-9.-]*'
        )
        OR EXISTS (
            SELECT 1
            FROM json_each(NEW.request_json, '$.ordered_universe')
            GROUP BY value
            HAVING count(*) <> 1
        )
        THEN RAISE(ABORT, 'session request universe is invalid') END;
    SELECT CASE WHEN length(json_extract(
            NEW.request_json,
            '$.request_window_start_date'
        )) <> 10
        OR json_extract(NEW.request_json, '$.request_window_start_date')
            NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        OR substr(json_extract(
            NEW.request_json,
            '$.request_window_start_date'
        ), 1, 4) NOT BETWEEN '0001' AND '9999'
        OR strftime(
            '%Y-%m-%d',
            json_extract(NEW.request_json, '$.request_window_start_date')
        ) IS NOT json_extract(NEW.request_json, '$.request_window_start_date')
        OR length(json_extract(NEW.request_json, '$.request_window_end_date')) <> 10
        OR json_extract(NEW.request_json, '$.request_window_end_date')
            NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        OR substr(json_extract(
            NEW.request_json,
            '$.request_window_end_date'
        ), 1, 4) NOT BETWEEN '0001' AND '9999'
        OR strftime(
            '%Y-%m-%d',
            json_extract(NEW.request_json, '$.request_window_end_date')
        ) IS NOT json_extract(NEW.request_json, '$.request_window_end_date')
        OR length(json_extract(NEW.request_json, '$.target_session_date')) <> 10
        OR json_extract(NEW.request_json, '$.target_session_date')
            NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        OR substr(json_extract(
            NEW.request_json,
            '$.target_session_date'
        ), 1, 4) NOT BETWEEN '0001' AND '9999'
        OR strftime(
            '%Y-%m-%d',
            json_extract(NEW.request_json, '$.target_session_date')
        ) IS NOT json_extract(NEW.request_json, '$.target_session_date')
        OR json_extract(NEW.request_json, '$.request_window_start_date')
            > json_extract(NEW.request_json, '$.request_window_end_date')
        OR json_extract(NEW.request_json, '$.request_window_end_date')
            >= json_extract(NEW.request_json, '$.target_session_date')
        THEN RAISE(ABORT, 'session request date window is invalid') END;
    SELECT CASE WHEN CAST(NEW.request_json AS TEXT) IS NOT (
        '{"bar_interval":'
        || json_quote(json_extract(NEW.request_json, '$.bar_interval'))
        || ',"child_operation_version":'
        || json_quote(json_extract(NEW.request_json, '$.child_operation_version'))
        || ',"ordered_universe":'
        || (SELECT json_group_array(value)
            FROM json_each(NEW.request_json, '$.ordered_universe'))
        || ',"output_policy_version":'
        || json_quote(json_extract(NEW.request_json, '$.output_policy_version'))
        || ',"permitted_provider_operation":'
        || json_quote(json_extract(
            NEW.request_json,
            '$.permitted_provider_operation'
        ))
        || ',"provider_id":'
        || json_quote(json_extract(NEW.request_json, '$.provider_id'))
        || ',"request_limit":'
        || json_extract(NEW.request_json, '$.request_limit')
        || ',"request_window_end_date":'
        || json_quote(json_extract(NEW.request_json, '$.request_window_end_date'))
        || ',"request_window_start_date":'
        || json_quote(json_extract(NEW.request_json, '$.request_window_start_date'))
        || ',"target_session_date":'
        || json_quote(json_extract(NEW.request_json, '$.target_session_date'))
        || '}'
    ) THEN RAISE(ABORT, 'session request bytes are not canonical') END;
    SELECT CASE WHEN sha256(NEW.request_json) IS NOT NEW.request_digest
        THEN RAISE(ABORT, 'session request digest is invalid') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM authority_metadata m
        WHERE m.authority_epoch_id = NEW.authority_epoch_id
          AND m.authority_policy_version IS NEW.authority_policy_version
          AND m.claim_policy_version IS NEW.claim_policy_version
          AND m.provider_id = 'alpaca-market-data'
          AND m.permitted_provider_operation =
              'historical-stock-bars-v2-raw-usd-no-asof'
          AND json_extract(NEW.request_json, '$.provider_id') IS m.provider_id
          AND json_extract(
              NEW.request_json,
              '$.permitted_provider_operation'
          ) IS m.permitted_provider_operation
          AND NEW.created_at_utc >= m.created_at_utc
    ) THEN RAISE(ABORT, 'session binding differs from metadata') END;
END;

CREATE TRIGGER sessions_immutable_fields
BEFORE UPDATE ON sessions
WHEN NEW.session_id <> OLD.session_id
  OR NEW.authority_epoch_id <> OLD.authority_epoch_id
  OR NEW.session_schema <> OLD.session_schema
  OR NEW.authority_policy_version <> OLD.authority_policy_version
  OR NEW.claim_policy_version <> OLD.claim_policy_version
  OR NEW.target_session_date <> OLD.target_session_date
  OR NEW.request_json IS NOT OLD.request_json
  OR NEW.request_digest IS NOT OLD.request_digest
  OR NEW.created_at_utc <> OLD.created_at_utc
BEGIN
    SELECT RAISE(ABORT, 'session identity and evidence are immutable');
END;

CREATE TRIGGER sessions_state_guard
BEFORE UPDATE OF state ON sessions
WHEN NOT (
    NEW.state = OLD.state
    OR (OLD.state = 'OPEN'
        AND NEW.state = 'SUCCESS_SELECTED'
        AND EXISTS (
            SELECT 1 FROM session_selections ss
            WHERE ss.session_id = OLD.session_id
        ))
    OR (OLD.state = 'OPEN'
        AND NEW.state = 'CLOSED'
        AND EXISTS (
            SELECT 1 FROM manual_recoveries mr
            WHERE mr.session_id = OLD.session_id
              AND mr.target_kind = 'SESSION'
              AND mr.target_id = OLD.session_id
              AND mr.action = 'CLOSE_SESSION'
              AND mr.predecessor_state = 'OPEN'
              AND mr.resulting_state = 'CLOSED'
        )
        AND NOT EXISTS (
            SELECT 1 FROM attempts a
            WHERE a.session_id = OLD.session_id
              AND a.state NOT IN (
                  'TERMINAL_RECORDED', 'SUCCESS_SELECTED', 'CLOSED'
              )
        )
        AND NOT EXISTS (
            SELECT 1
            FROM attempts a
            WHERE a.session_id = OLD.session_id
              AND a.state = 'TERMINAL_RECORDED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM provider_call_claims c
                  JOIN launch_reservations r ON r.claim_id = c.claim_id
                  JOIN terminals t
                    ON t.launch_reservation_id = r.launch_reservation_id
                  WHERE c.attempt_id = a.attempt_id
                    AND c.state = 'COMMITTED'
                    AND r.reservation_state = 'TERMINAL_RECORDED'
              )
        )
        AND NOT EXISTS (
            SELECT 1
            FROM attempts a
            WHERE a.session_id = OLD.session_id
              AND a.state = 'SUCCESS_SELECTED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM provider_call_claims c
                  JOIN launch_reservations r ON r.claim_id = c.claim_id
                  JOIN terminals t
                    ON t.launch_reservation_id = r.launch_reservation_id
                  JOIN session_selections ss ON ss.terminal_id = t.terminal_id
                  WHERE c.attempt_id = a.attempt_id
                    AND c.state = 'COMMITTED'
                    AND r.reservation_state = 'TERMINAL_RECORDED'
                    AND ss.session_id = OLD.session_id
              )
        )
        AND NOT EXISTS (
            SELECT 1
            FROM attempts a
            WHERE a.session_id = OLD.session_id
              AND a.state = 'CLOSED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM provider_call_claims c
                  JOIN launch_reservations r ON r.claim_id = c.claim_id
                  JOIN terminals t
                    ON t.launch_reservation_id = r.launch_reservation_id
                  WHERE c.attempt_id = a.attempt_id
                    AND c.state = 'COMMITTED'
                    AND r.reservation_state = 'TERMINAL_RECORDED'
              )
        )
        AND NOT EXISTS (
            SELECT 1
            FROM terminals t
            JOIN launch_reservations r
              ON r.launch_reservation_id = t.launch_reservation_id
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            WHERE a.session_id = OLD.session_id
              AND t.terminal_state = 'AMBIGUOUS'
        ))
    OR (OLD.state = 'SUCCESS_SELECTED'
        AND NEW.state = 'CLOSED'
        AND EXISTS (
            SELECT 1 FROM session_selections ss
            WHERE ss.session_id = OLD.session_id
        ))
)
BEGIN
    SELECT RAISE(ABORT, 'session state requires its durable projection fact');
END;

CREATE TRIGGER sessions_close_facts_guard
BEFORE UPDATE ON sessions
WHEN NOT (
    (NEW.closed_at_utc IS OLD.closed_at_utc
     AND NEW.close_reason IS OLD.close_reason)
    OR (OLD.closed_at_utc IS NULL
        AND OLD.close_reason IS NULL
        AND NEW.state = 'CLOSED'
        AND NEW.closed_at_utc IS NOT NULL
        AND NEW.close_reason IS NOT NULL
        AND (
            (OLD.state = 'OPEN'
             AND EXISTS (
                 SELECT 1 FROM manual_recoveries mr
                 WHERE mr.session_id = OLD.session_id
                   AND mr.target_kind = 'SESSION'
                   AND mr.target_id = OLD.session_id
                   AND mr.action = 'CLOSE_SESSION'
                   AND NEW.closed_at_utc >= mr.created_at_utc
             ))
            OR (OLD.state = 'SUCCESS_SELECTED'
                AND EXISTS (
                    SELECT 1 FROM session_selections ss
                    WHERE ss.session_id = OLD.session_id
                      AND NEW.closed_at_utc >= ss.selected_at_utc
                ))
        ))
)
BEGIN
    SELECT RAISE(ABORT, 'session close facts are write-once');
END;

CREATE TRIGGER sessions_attempt_counter_guard
BEFORE UPDATE OF next_attempt_ordinal ON sessions
WHEN NEW.next_attempt_ordinal = OLD.next_attempt_ordinal
  OR NEW.next_attempt_ordinal <> OLD.next_attempt_ordinal + 1
  OR NOT EXISTS (
      SELECT 1 FROM attempts
      WHERE session_id = OLD.session_id AND ordinal = OLD.next_attempt_ordinal
  )
  OR NEW.next_attempt_ordinal <> (
      SELECT count(*) FROM attempts WHERE session_id = OLD.session_id
  )
BEGIN
    SELECT RAISE(ABORT, 'attempt counter is trigger-owned and must advance exactly once');
END;

CREATE TRIGGER sessions_recovery_counter_guard
BEFORE UPDATE OF next_recovery_ordinal ON sessions
WHEN NEW.next_recovery_ordinal = OLD.next_recovery_ordinal
  OR NEW.next_recovery_ordinal <> OLD.next_recovery_ordinal + 1
  OR NOT EXISTS (
      SELECT 1 FROM manual_recoveries
      WHERE session_id = OLD.session_id
        AND recovery_ordinal = OLD.next_recovery_ordinal
  )
  OR NEW.next_recovery_ordinal <> (
      SELECT count(*) FROM manual_recoveries WHERE session_id = OLD.session_id
  )
BEGIN
    SELECT RAISE(ABORT, 'recovery counter is trigger-owned and must advance exactly once');
END;

CREATE TRIGGER sessions_no_delete
BEFORE DELETE ON sessions
BEGIN
    SELECT RAISE(ABORT, 'sessions cannot be deleted');
END;

CREATE TRIGGER attempts_before_insert
BEFORE INSERT ON attempts
FOR EACH ROW
BEGIN
    SELECT CASE WHEN sha256(NEW.request_json) IS NOT NEW.request_digest
        THEN RAISE(ABORT, 'attempt request digest is invalid') END;
    SELECT CASE WHEN sha256(NEW.allocation_evidence_json)
        IS NOT NEW.allocation_evidence_digest
        THEN RAISE(ABORT, 'attempt allocation evidence digest is invalid') END;
    SELECT CASE WHEN sha256(NEW.attempt_evidence_json)
        IS NOT NEW.attempt_evidence_digest
        THEN RAISE(ABORT, 'attempt evidence digest is invalid') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM sessions
        WHERE session_id = NEW.session_id AND state = 'OPEN'
    ) THEN RAISE(ABORT, 'attempt session is not open') END;
    SELECT CASE WHEN NEW.ordinal <> (
        SELECT next_attempt_ordinal FROM sessions WHERE session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'attempt ordinal is not the session counter') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM sessions s
        JOIN authority_metadata m
          ON m.authority_epoch_id = s.authority_epoch_id
        WHERE s.session_id = NEW.session_id
          AND s.request_json IS NEW.request_json
          AND s.request_digest IS NEW.request_digest
          AND s.claim_policy_version IS NEW.attempt_policy_version
          AND m.provider_id IS NEW.provider_id
          AND m.permitted_provider_operation IS NEW.permitted_provider_operation
          AND NEW.created_at_utc >= s.created_at_utc
    ) THEN RAISE(ABORT, 'attempt parent binding differs from session or metadata') END;
    SELECT CASE WHEN NEW.state <> 'ALLOCATED'
        THEN RAISE(ABORT, 'new attempts must start allocated') END;
    SELECT CASE WHEN NEW.provider_call_budget <> 1
        THEN RAISE(ABORT, 'provider call budget must be one') END;
END;

CREATE TRIGGER attempts_after_insert
AFTER INSERT ON attempts
FOR EACH ROW
BEGIN
    UPDATE sessions
    SET next_attempt_ordinal = next_attempt_ordinal + 1
    WHERE session_id = NEW.session_id
      AND next_attempt_ordinal = NEW.ordinal;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM sessions
        WHERE session_id = NEW.session_id
          AND next_attempt_ordinal = NEW.ordinal + 1
    ) THEN RAISE(ABORT, 'attempt counter was not incremented exactly once') END;
END;

CREATE TRIGGER attempts_immutable_fields
BEFORE UPDATE ON attempts
WHEN NEW.attempt_id <> OLD.attempt_id
  OR NEW.session_id <> OLD.session_id
  OR NEW.ordinal <> OLD.ordinal
  OR NEW.provider_id <> OLD.provider_id
  OR NEW.permitted_provider_operation <> OLD.permitted_provider_operation
  OR NEW.provider_call_budget <> OLD.provider_call_budget
  OR NEW.request_json IS NOT OLD.request_json
  OR NEW.request_digest IS NOT OLD.request_digest
  OR NEW.attempt_schema <> OLD.attempt_schema
  OR NEW.attempt_policy_version <> OLD.attempt_policy_version
  OR NEW.allocation_evidence_json IS NOT OLD.allocation_evidence_json
  OR NEW.allocation_evidence_digest IS NOT OLD.allocation_evidence_digest
  OR NEW.attempt_evidence_json IS NOT OLD.attempt_evidence_json
  OR NEW.attempt_evidence_digest IS NOT OLD.attempt_evidence_digest
  OR NEW.created_at_utc <> OLD.created_at_utc
BEGIN
    SELECT RAISE(ABORT, 'attempt identity and evidence are immutable');
END;

CREATE TRIGGER attempts_state_guard
BEFORE UPDATE OF state ON attempts
WHEN NOT (
    NEW.state = OLD.state
    OR (OLD.state = 'ALLOCATED'
        AND NEW.state = 'CLAIM_COMMITTED'
        AND EXISTS (
            SELECT 1 FROM provider_call_claims c
            WHERE c.attempt_id = OLD.attempt_id
              AND c.state = 'COMMITTED'
              AND c.provider_id IS OLD.provider_id
              AND c.permitted_provider_operation IS OLD.permitted_provider_operation
              AND c.provider_call_budget = OLD.provider_call_budget
              AND c.claim_policy_version IS OLD.attempt_policy_version
              AND c.request_json IS OLD.request_json
              AND c.request_digest IS OLD.request_digest
        ))
    OR (OLD.state = 'CLAIM_COMMITTED'
        AND NEW.state = 'LAUNCH_RESERVED'
        AND EXISTS (
            SELECT 1
            FROM provider_call_claims c
            JOIN launch_reservations r ON r.claim_id = c.claim_id
            WHERE c.attempt_id = OLD.attempt_id
              AND c.state = 'COMMITTED'
              AND r.reservation_state = 'COMMITTED'
              AND r.request_digest IS c.request_digest
              AND r.claim_policy_version IS c.claim_policy_version
        ))
    OR (OLD.state = 'LAUNCH_RESERVED'
        AND NEW.state = 'LAUNCH_MAY_HAVE_OCCURRED'
        AND EXISTS (
            SELECT 1
            FROM manual_recoveries mr
            JOIN provider_call_claims c ON c.attempt_id = OLD.attempt_id
            JOIN launch_reservations r ON r.claim_id = c.claim_id
            JOIN launch_executions e
              ON e.launch_reservation_id = r.launch_reservation_id
            JOIN sessions s ON s.session_id = OLD.session_id
            WHERE mr.session_id = OLD.session_id
              AND mr.target_kind = 'ATTEMPT'
              AND mr.target_id = OLD.attempt_id
              AND mr.action = 'RECORD_ATTEMPT_AMBIGUITY'
              AND mr.predecessor_state = 'LAUNCH_RESERVED'
              AND mr.resulting_state = 'AMBIGUITY_RECORDED'
              AND c.state = 'COMMITTED'
              AND r.reservation_state = 'PROCESS_CREATED'
              AND e.phase IN ('RESUME_RECORDED', 'POST_RESUME_AMBIGUOUS')
              AND s.state = 'OPEN'
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
        ))
    OR (OLD.state IN ('LAUNCH_RESERVED', 'LAUNCH_MAY_HAVE_OCCURRED')
        AND NEW.state = 'TERMINAL_RECORDED'
        AND EXISTS (
            SELECT 1
            FROM provider_call_claims c
            JOIN launch_reservations r ON r.claim_id = c.claim_id
            JOIN terminals t
              ON t.launch_reservation_id = r.launch_reservation_id
            WHERE c.attempt_id = OLD.attempt_id
              AND c.state = 'COMMITTED'
              AND r.reservation_state = 'TERMINAL_RECORDED'
        ))
    OR (OLD.state = 'TERMINAL_RECORDED'
        AND NEW.state = 'SUCCESS_SELECTED'
        AND EXISTS (
            SELECT 1
            FROM provider_call_claims c
            JOIN launch_reservations r ON r.claim_id = c.claim_id
            JOIN terminals t
              ON t.launch_reservation_id = r.launch_reservation_id
            JOIN session_selections ss ON ss.terminal_id = t.terminal_id
            WHERE c.attempt_id = OLD.attempt_id
              AND ss.session_id = OLD.session_id
              AND t.terminal_state = 'SUCCEEDED'
              AND t.provider_call_disposition = 'CONFIRMED'
        ))
    OR (OLD.state IN ('TERMINAL_RECORDED', 'SUCCESS_SELECTED')
        AND NEW.state = 'CLOSED'
        AND EXISTS (
            SELECT 1 FROM sessions s
            WHERE s.session_id = OLD.session_id
              AND s.state = 'CLOSED'
        )
        AND EXISTS (
            SELECT 1
            FROM provider_call_claims c
            JOIN launch_reservations r ON r.claim_id = c.claim_id
            JOIN terminals t
              ON t.launch_reservation_id = r.launch_reservation_id
            WHERE c.attempt_id = OLD.attempt_id
              AND (
                  OLD.state = 'TERMINAL_RECORDED'
                  OR EXISTS (
                      SELECT 1 FROM session_selections ss
                      WHERE ss.session_id = OLD.session_id
                        AND ss.terminal_id = t.terminal_id
                  )
              )
        ))
)
BEGIN
    SELECT RAISE(ABORT, 'attempt state requires its durable projection fact');
END;

CREATE TRIGGER attempts_no_delete
BEFORE DELETE ON attempts
BEGIN
    SELECT RAISE(ABORT, 'attempts cannot be deleted');
END;

CREATE TRIGGER provider_call_claims_no_update
BEFORE UPDATE ON provider_call_claims
BEGIN
    SELECT RAISE(ABORT, 'provider call claims are immutable');
END;

CREATE TRIGGER provider_call_claims_before_insert
BEFORE INSERT ON provider_call_claims
FOR EACH ROW
BEGIN
    SELECT CASE WHEN sha256(NEW.request_json) IS NOT NEW.request_digest
        THEN RAISE(ABORT, 'claim request digest is invalid') END;
    SELECT CASE WHEN sha256(NEW.claim_evidence_json) IS NOT NEW.claim_evidence_digest
        THEN RAISE(ABORT, 'claim evidence digest is invalid') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM attempts a
        JOIN sessions s ON s.session_id = a.session_id
        WHERE a.attempt_id = NEW.attempt_id
          AND a.state = 'ALLOCATED'
          AND s.state = 'OPEN'
          AND NEW.state = 'COMMITTED'
          AND a.provider_id IS NEW.provider_id
          AND a.permitted_provider_operation IS NEW.permitted_provider_operation
          AND a.provider_call_budget = NEW.provider_call_budget
          AND a.attempt_policy_version IS NEW.claim_policy_version
          AND a.request_json IS NEW.request_json
          AND a.request_digest IS NEW.request_digest
          AND NEW.committed_at_utc >= a.created_at_utc
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM terminals t
              JOIN launch_reservations r
                ON r.launch_reservation_id = t.launch_reservation_id
              JOIN provider_call_claims prior_success
                ON prior_success.claim_id = r.claim_id
              JOIN attempts prior_attempt
                ON prior_attempt.attempt_id = prior_success.attempt_id
              WHERE prior_attempt.session_id = s.session_id
                AND t.terminal_state = 'SUCCEEDED'
          )
          AND NOT EXISTS (
              SELECT 1
              FROM provider_call_claims prior_claim
              JOIN attempts prior_attempt
                ON prior_attempt.attempt_id = prior_claim.attempt_id
              WHERE prior_attempt.session_id = s.session_id
                AND NOT EXISTS (
                    SELECT 1
                    FROM launch_reservations safe_reservation
                    JOIN terminals safe_terminal
                      ON safe_terminal.launch_reservation_id = safe_reservation.launch_reservation_id
                    WHERE safe_reservation.claim_id = prior_claim.claim_id
                      AND prior_attempt.state = 'TERMINAL_RECORDED'
                      AND safe_reservation.reservation_state = 'TERMINAL_RECORDED'
                      AND safe_reservation.process_creation_failure_json IS NOT NULL
                      AND safe_reservation.process_creation_failure_digest IS NOT NULL
                      AND sha256(safe_reservation.process_creation_failure_json)
                          IS safe_reservation.process_creation_failure_digest
                      AND safe_reservation.process_intent_json IS NOT NULL
                      AND safe_reservation.process_intent_digest IS NOT NULL
                      AND sha256(safe_reservation.process_intent_json)
                          IS safe_reservation.process_intent_digest
                      AND safe_terminal.terminal_state = 'FAILED'
                      AND safe_terminal.provider_call_disposition = 'NOT_STARTED'
                      AND safe_terminal.snapshot_digest IS NULL
                      AND NOT EXISTS (
                          SELECT 1
                          FROM launch_executions prior_execution
                          WHERE prior_execution.launch_reservation_id = safe_reservation.launch_reservation_id
                      )
                )
          )
    ) THEN RAISE(ABORT, 'claim admission policy rejected') END;
END;

CREATE TRIGGER provider_call_claims_no_delete
BEFORE DELETE ON provider_call_claims
BEGIN
    SELECT RAISE(ABORT, 'provider call claims cannot be deleted');
END;

CREATE TRIGGER launch_reservations_immutable_fields
BEFORE UPDATE ON launch_reservations
WHEN NEW.launch_reservation_id <> OLD.launch_reservation_id
  OR NEW.claim_id <> OLD.claim_id
  OR NEW.launch_reservation_schema <> OLD.launch_reservation_schema
  OR NEW.application_release_version <> OLD.application_release_version
  OR NEW.authority_policy_version <> OLD.authority_policy_version
  OR NEW.claim_policy_version <> OLD.claim_policy_version
  OR NEW.request_digest IS NOT OLD.request_digest
  OR NEW.reservation_evidence_json IS NOT OLD.reservation_evidence_json
  OR NEW.reservation_evidence_digest IS NOT OLD.reservation_evidence_digest
  OR NEW.committed_at_utc <> OLD.committed_at_utc
BEGIN
    SELECT RAISE(ABORT, 'launch reservation identity and evidence are immutable');
END;

CREATE TRIGGER launch_reservations_before_insert
BEFORE INSERT ON launch_reservations
FOR EACH ROW
BEGIN
    SELECT CASE WHEN sha256(NEW.reservation_evidence_json)
        IS NOT NEW.reservation_evidence_digest
        THEN RAISE(ABORT, 'reservation evidence digest is invalid') END;
    SELECT CASE WHEN NOT (
        NEW.reservation_state = 'COMMITTED'
        AND NEW.process_intent_json IS NULL
        AND NEW.process_intent_digest IS NULL
        AND NEW.process_intent_committed_at_utc IS NULL
        AND NEW.process_creation_failure_json IS NULL
        AND NEW.process_creation_failure_digest IS NULL
        AND NEW.outcome_recorded_at_utc IS NULL
    ) THEN RAISE(ABORT, 'new reservations must start as committed fences') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM provider_call_claims c
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE c.claim_id = NEW.claim_id
          AND c.state = 'COMMITTED'
          AND a.state = 'CLAIM_COMMITTED'
          AND s.state = 'OPEN'
          AND c.request_digest IS NEW.request_digest
          AND c.claim_policy_version IS NEW.claim_policy_version
          AND s.authority_policy_version IS NEW.authority_policy_version
          AND NEW.committed_at_utc >= c.committed_at_utc
    ) THEN RAISE(ABORT, 'reservation parent binding differs from claim lineage') END;
END;

CREATE TRIGGER launch_reservations_process_intent_append_only
BEFORE UPDATE ON launch_reservations
WHEN OLD.process_intent_json IS NOT NEW.process_intent_json
  OR OLD.process_intent_digest IS NOT NEW.process_intent_digest
  OR OLD.process_intent_committed_at_utc IS NOT NEW.process_intent_committed_at_utc
BEGIN
    SELECT CASE WHEN NOT (
        OLD.process_intent_json IS NULL
        AND OLD.process_intent_digest IS NULL
        AND OLD.process_intent_committed_at_utc IS NULL
        AND NEW.process_intent_json IS NOT NULL
        AND NEW.process_intent_digest IS NOT NULL
        AND NEW.process_intent_committed_at_utc IS NOT NULL
        AND NEW.process_intent_committed_at_utc >= OLD.committed_at_utc
        AND sha256(NEW.process_intent_json) IS NEW.process_intent_digest
        AND CAST(NEW.process_intent_json AS TEXT) =
            '{"authority_policy_version":"' || OLD.authority_policy_version ||
            '","claim_policy_version":"' || OLD.claim_policy_version ||
            '","launch_reservation_id":"' || OLD.launch_reservation_id ||
            '","process_operation":"CreateProcessW","request_digest":"' ||
            lower(hex(OLD.request_digest)) || '","schema":1}'
        AND OLD.reservation_state = 'COMMITTED'
        AND NEW.reservation_state = 'PROCESS_INTENT_COMMITTED'
        AND OLD.outcome_recorded_at_utc IS NULL
        AND NEW.outcome_recorded_at_utc IS NULL
    ) THEN RAISE(ABORT, 'process intent is append-only') END;
END;

CREATE TRIGGER launch_reservations_failure_evidence_guard
BEFORE UPDATE ON launch_reservations
WHEN OLD.process_creation_failure_json IS NOT NEW.process_creation_failure_json
  OR OLD.process_creation_failure_digest IS NOT NEW.process_creation_failure_digest
BEGIN
    SELECT CASE WHEN NOT (
        OLD.process_creation_failure_json IS NULL
        AND OLD.process_creation_failure_digest IS NULL
        AND NEW.process_creation_failure_json IS NOT NULL
        AND NEW.process_creation_failure_digest IS NOT NULL
        AND sha256(NEW.process_creation_failure_json) IS NEW.process_creation_failure_digest
        AND OLD.reservation_state = 'PROCESS_INTENT_COMMITTED'
        AND NEW.reservation_state = 'PROCESS_CREATION_FAILED'
        AND OLD.process_intent_json IS NOT NULL
        AND OLD.process_intent_digest IS NOT NULL
        AND sha256(OLD.process_intent_json) IS OLD.process_intent_digest
        AND CAST(NEW.process_creation_failure_json AS TEXT) =
            '{"creation_result":"NOT_CREATED","process_intent_digest":"' ||
            lower(hex(OLD.process_intent_digest)) ||
            '","reservation_id":"' || OLD.launch_reservation_id ||
            '","schema":1}'
        AND OLD.outcome_recorded_at_utc IS NULL
        AND NEW.outcome_recorded_at_utc IS NOT NULL
    ) THEN RAISE(ABORT, 'process creation failure evidence is write-once') END;
END;

CREATE TRIGGER launch_reservations_outcome_timestamp_guard
BEFORE UPDATE ON launch_reservations
WHEN NOT (
    (OLD.outcome_recorded_at_utc IS NULL
     AND NEW.outcome_recorded_at_utc IS NULL
     AND NEW.reservation_state = OLD.reservation_state)
    OR (OLD.outcome_recorded_at_utc IS NULL
        AND NEW.outcome_recorded_at_utc IS NULL
        AND OLD.reservation_state = 'COMMITTED'
        AND NEW.reservation_state = 'PROCESS_INTENT_COMMITTED')
    OR (OLD.outcome_recorded_at_utc IS NULL
        AND NEW.outcome_recorded_at_utc IS NOT NULL
        AND OLD.reservation_state IN ('COMMITTED', 'PROCESS_INTENT_COMMITTED')
        AND NEW.reservation_state IN (
            'PROCESS_CREATED', 'PROCESS_CREATION_FAILED', 'MANUAL_REVIEW'
        )
        AND (
            (OLD.reservation_state = 'COMMITTED'
             AND NEW.reservation_state = 'MANUAL_REVIEW'
             AND NEW.outcome_recorded_at_utc >= OLD.committed_at_utc
             AND EXISTS (
                 SELECT 1 FROM manual_recoveries mr
                 WHERE mr.target_kind = 'LAUNCH_RESERVATION'
                   AND mr.target_id = OLD.launch_reservation_id
                   AND mr.action = 'CLASSIFY_LAUNCH_RESERVATION'
                   AND NEW.outcome_recorded_at_utc >= mr.created_at_utc
             ))
            OR (OLD.reservation_state = 'PROCESS_INTENT_COMMITTED'
                AND NEW.reservation_state = 'PROCESS_CREATED'
                AND NEW.outcome_recorded_at_utc >= OLD.process_intent_committed_at_utc
                AND EXISTS (
                    SELECT 1 FROM launch_executions e
                    WHERE e.launch_reservation_id = OLD.launch_reservation_id
                      AND NEW.outcome_recorded_at_utc >= e.created_at_utc
                ))
            OR (OLD.reservation_state = 'PROCESS_INTENT_COMMITTED'
                AND NEW.reservation_state = 'PROCESS_CREATION_FAILED'
                AND NEW.outcome_recorded_at_utc >= OLD.process_intent_committed_at_utc)
            OR (OLD.reservation_state = 'PROCESS_INTENT_COMMITTED'
                AND NEW.reservation_state = 'MANUAL_REVIEW'
                AND NEW.outcome_recorded_at_utc >= OLD.process_intent_committed_at_utc
                AND EXISTS (
                    SELECT 1 FROM manual_recoveries mr
                    WHERE mr.target_kind = 'LAUNCH_RESERVATION'
                      AND mr.target_id = OLD.launch_reservation_id
                      AND mr.action = 'CLASSIFY_PROCESS_OUTCOME_UNKNOWN'
                      AND NEW.outcome_recorded_at_utc >= mr.created_at_utc
                ))
        ))
    OR (OLD.outcome_recorded_at_utc IS NOT NULL
        AND NEW.outcome_recorded_at_utc IS OLD.outcome_recorded_at_utc)
)
BEGIN
    SELECT RAISE(ABORT, 'reservation outcome timestamp is write-once');
END;

CREATE TRIGGER launch_reservations_state_guard
BEFORE UPDATE OF reservation_state ON launch_reservations
WHEN NOT (
    NEW.reservation_state = OLD.reservation_state
    OR (OLD.reservation_state = 'COMMITTED'
        AND NEW.reservation_state = 'PROCESS_INTENT_COMMITTED'
        AND NEW.process_intent_json IS NOT NULL
        AND NEW.process_intent_digest IS NOT NULL
        AND NEW.process_intent_committed_at_utc IS NOT NULL
        AND sha256(NEW.process_intent_json) IS NEW.process_intent_digest
        AND EXISTS (
            SELECT 1
            FROM provider_call_claims c
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE c.claim_id = OLD.claim_id
              AND c.state = 'COMMITTED'
              AND a.state = 'LAUNCH_RESERVED'
              AND s.state = 'OPEN'
              AND c.request_digest IS OLD.request_digest
              AND a.request_digest IS OLD.request_digest
              AND s.request_digest IS OLD.request_digest
              AND c.claim_policy_version IS OLD.claim_policy_version
              AND a.attempt_policy_version IS OLD.claim_policy_version
              AND s.claim_policy_version IS OLD.claim_policy_version
              AND s.authority_policy_version IS OLD.authority_policy_version
              AND NOT EXISTS (
                  SELECT 1 FROM launch_executions e
                  WHERE e.launch_reservation_id = OLD.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = OLD.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
        ))
    OR (OLD.reservation_state = 'COMMITTED'
        AND NEW.reservation_state = 'MANUAL_REVIEW'
        AND EXISTS (
            SELECT 1
            FROM manual_recoveries mr
            JOIN provider_call_claims c ON c.claim_id = OLD.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE mr.session_id = a.session_id
              AND mr.target_kind = 'LAUNCH_RESERVATION'
              AND mr.target_id = OLD.launch_reservation_id
              AND mr.action = 'CLASSIFY_LAUNCH_RESERVATION'
              AND mr.predecessor_state = 'COMMITTED'
              AND mr.resulting_state = 'MANUAL_REVIEW'
              AND c.state = 'COMMITTED'
              AND a.state = 'LAUNCH_RESERVED'
              AND s.state = 'OPEN'
              AND NOT EXISTS (
                  SELECT 1 FROM launch_executions e
                  WHERE e.launch_reservation_id = OLD.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = OLD.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
        ))
    OR (OLD.reservation_state = 'PROCESS_INTENT_COMMITTED'
        AND NEW.reservation_state = 'PROCESS_CREATED'
        AND OLD.process_intent_json IS NOT NULL
        AND OLD.process_intent_digest IS NOT NULL
        AND OLD.process_intent_committed_at_utc IS NOT NULL
        AND sha256(OLD.process_intent_json) IS OLD.process_intent_digest
        AND EXISTS (
            SELECT 1 FROM launch_executions e
            WHERE e.launch_reservation_id = OLD.launch_reservation_id
              AND e.phase = 'PRE_RESUME_READY'
              AND sha256(e.process_creation_json) IS e.process_creation_digest
              AND sha256(e.job_object_json) IS e.job_object_digest
              AND sha256(e.resume_authorization_json)
                  IS e.resume_authorization_digest
        ))
    OR (OLD.reservation_state = 'PROCESS_INTENT_COMMITTED'
        AND NEW.reservation_state = 'PROCESS_CREATION_FAILED'
        AND OLD.process_intent_json IS NOT NULL
        AND OLD.process_intent_digest IS NOT NULL
        AND OLD.process_intent_committed_at_utc IS NOT NULL
        AND sha256(OLD.process_intent_json) IS OLD.process_intent_digest
        AND NEW.process_creation_failure_json IS NOT NULL
        AND NEW.process_creation_failure_digest IS NOT NULL
        AND sha256(NEW.process_creation_failure_json)
            IS NEW.process_creation_failure_digest
        AND NOT EXISTS (
            SELECT 1 FROM launch_executions e
            WHERE e.launch_reservation_id = OLD.launch_reservation_id
        ))
    OR (OLD.reservation_state = 'PROCESS_INTENT_COMMITTED'
        AND NEW.reservation_state = 'MANUAL_REVIEW'
        AND OLD.process_intent_json IS NOT NULL
        AND OLD.process_intent_digest IS NOT NULL
        AND OLD.process_intent_committed_at_utc IS NOT NULL
        AND sha256(OLD.process_intent_json) IS OLD.process_intent_digest
        AND EXISTS (
            SELECT 1
            FROM manual_recoveries mr
            JOIN provider_call_claims c ON c.claim_id = OLD.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE mr.session_id = a.session_id
              AND mr.target_kind = 'LAUNCH_RESERVATION'
              AND mr.target_id = OLD.launch_reservation_id
              AND mr.action = 'CLASSIFY_PROCESS_OUTCOME_UNKNOWN'
              AND mr.predecessor_state = 'PROCESS_INTENT_COMMITTED'
              AND mr.resulting_state = 'MANUAL_REVIEW'
              AND c.state = 'COMMITTED'
              AND a.state = 'LAUNCH_RESERVED'
              AND s.state = 'OPEN'
              AND OLD.process_creation_failure_json IS NULL
              AND OLD.process_creation_failure_digest IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM launch_executions e
                  WHERE e.launch_reservation_id = OLD.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = OLD.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
        ))
    OR (OLD.reservation_state = 'PROCESS_CREATED'
        AND NEW.reservation_state = 'MANUAL_REVIEW'
        AND EXISTS (
            SELECT 1
            FROM manual_recoveries mr
            JOIN provider_call_claims c ON c.claim_id = OLD.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            JOIN launch_executions e
              ON e.launch_reservation_id = OLD.launch_reservation_id
            WHERE mr.session_id = a.session_id
              AND mr.target_kind = 'LAUNCH_RESERVATION'
              AND mr.target_id = OLD.launch_reservation_id
              AND mr.predecessor_state = 'PROCESS_CREATED'
              AND mr.resulting_state = 'MANUAL_REVIEW'
              AND c.state = 'COMMITTED'
              AND a.state = 'LAUNCH_RESERVED'
              AND s.state = 'OPEN'
              AND (
                  (mr.action = 'CLASSIFY_PRE_RESUME_READY'
                   AND e.phase = 'PRE_RESUME_READY'
                   AND e.resume_intent_json IS NULL
                   AND e.resume_intent_digest IS NULL
                   AND e.resume_intent_committed_at_utc IS NULL
                   AND e.post_resume_json IS NULL
                   AND e.post_resume_digest IS NULL
                   AND e.cleanup_json IS NULL
                   AND e.cleanup_digest IS NULL)
                  OR (mr.action = 'CLASSIFY_RESUME_OUTCOME_UNKNOWN'
                      AND e.phase = 'RESUME_INTENT_COMMITTED'
                      AND e.resume_intent_json IS NOT NULL
                      AND e.resume_intent_digest IS NOT NULL
                      AND sha256(e.resume_intent_json) IS e.resume_intent_digest
                      AND e.resume_intent_committed_at_utc IS NOT NULL
                      AND e.post_resume_json IS NULL
                      AND e.post_resume_digest IS NULL
                      AND e.cleanup_json IS NULL
                      AND e.cleanup_digest IS NULL)
              )
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = OLD.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
        ))
    OR (OLD.reservation_state IN (
            'PROCESS_CREATED', 'PROCESS_CREATION_FAILED', 'MANUAL_REVIEW'
        )
        AND NEW.reservation_state = 'TERMINAL_RECORDED'
        AND EXISTS (
            SELECT 1 FROM terminals t
            WHERE t.launch_reservation_id = OLD.launch_reservation_id
        ))
)
BEGIN
    SELECT RAISE(ABORT, 'reservation state requires its durable projection fact');
END;

CREATE TRIGGER launch_reservations_no_delete
BEFORE DELETE ON launch_reservations
BEGIN
    SELECT RAISE(ABORT, 'launch reservations cannot be deleted');
END;

CREATE TRIGGER launch_executions_immutable_fields
BEFORE UPDATE ON launch_executions
WHEN NEW.launch_execution_id <> OLD.launch_execution_id
  OR NEW.launch_reservation_id <> OLD.launch_reservation_id
  OR NEW.launch_schema <> OLD.launch_schema
  OR NEW.application_release_version <> OLD.application_release_version
  OR NEW.authority_policy_version <> OLD.authority_policy_version
  OR NEW.process_creation_json IS NOT OLD.process_creation_json
  OR NEW.process_creation_digest IS NOT OLD.process_creation_digest
  OR NEW.job_object_json IS NOT OLD.job_object_json
  OR NEW.job_object_digest IS NOT OLD.job_object_digest
  OR NEW.resume_authorization_json IS NOT OLD.resume_authorization_json
  OR NEW.resume_authorization_digest IS NOT OLD.resume_authorization_digest
  OR NEW.created_at_utc <> OLD.created_at_utc
BEGIN
    SELECT RAISE(ABORT, 'launch execution identity and evidence are immutable');
END;

CREATE TRIGGER launch_executions_phase_guard
BEFORE UPDATE OF phase ON launch_executions
WHEN NOT (
    NEW.phase = OLD.phase
    OR (OLD.phase = 'PRE_RESUME_READY'
        AND NEW.phase = 'RESUME_INTENT_COMMITTED'
        AND NEW.resume_intent_json IS NOT NULL
        AND NEW.resume_intent_digest IS NOT NULL
        AND sha256(NEW.resume_intent_json) IS NEW.resume_intent_digest
        AND CAST(NEW.resume_intent_json AS TEXT) =
            '{"execution_id":"' || NEW.launch_execution_id ||
            '","resume_operation":"ResumeThread","schema":1}'
        AND EXISTS (
            SELECT 1
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE r.launch_reservation_id = NEW.launch_reservation_id
              AND r.reservation_state = 'PROCESS_CREATED'
              AND s.state = 'OPEN'
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
        ))
    OR (OLD.phase = 'RESUME_INTENT_COMMITTED'
        AND NEW.phase = 'RESUME_RECORDED'
        AND NEW.post_resume_json IS NOT NULL
        AND NEW.post_resume_digest IS NOT NULL
        AND sha256(NEW.post_resume_json) IS NEW.post_resume_digest
        AND CAST(NEW.post_resume_json AS TEXT) =
            '{"execution_id":"' || NEW.launch_execution_id ||
            '","resume_intent_digest":"' || lower(hex(NEW.resume_intent_digest)) ||
            '","resume_result":"RESUMED","schema":1}'
        AND NEW.cleanup_json IS NOT NULL
        AND NEW.cleanup_digest IS NOT NULL
        AND sha256(NEW.cleanup_json) IS NEW.cleanup_digest
        AND EXISTS (
            SELECT 1
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE r.launch_reservation_id = NEW.launch_reservation_id
              AND r.reservation_state = 'PROCESS_CREATED'
              AND s.state = 'OPEN'
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
        ))
    OR (OLD.phase = 'RESUME_RECORDED'
        AND NEW.phase = 'POST_RESUME_AMBIGUOUS'
        AND EXISTS (
            SELECT 1
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            JOIN manual_recoveries mr
              ON mr.session_id = a.session_id
             AND mr.target_kind = 'ATTEMPT'
             AND mr.target_id = a.attempt_id
            WHERE r.launch_reservation_id = OLD.launch_reservation_id
              AND mr.action = 'RECORD_ATTEMPT_AMBIGUITY'
              AND mr.predecessor_state = 'LAUNCH_RESERVED'
              AND mr.resulting_state = 'AMBIGUITY_RECORDED'
              AND c.state = 'COMMITTED'
              AND a.state = 'LAUNCH_RESERVED'
              AND r.reservation_state = 'PROCESS_CREATED'
              AND s.state = 'OPEN'
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
        ))
    OR (OLD.phase IN ('RESUME_RECORDED', 'POST_RESUME_AMBIGUOUS')
        AND NEW.phase = 'TERMINAL_RECORDED'
        AND EXISTS (
            SELECT 1 FROM terminals t
            WHERE t.launch_reservation_id = OLD.launch_reservation_id
        ))
    OR (OLD.phase IN ('POST_RESUME_AMBIGUOUS', 'TERMINAL_RECORDED')
        AND NEW.phase = 'CLOSED'
        AND EXISTS (
            SELECT 1
            FROM terminals t
            JOIN launch_reservations r
              ON r.launch_reservation_id = t.launch_reservation_id
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE t.launch_reservation_id = OLD.launch_reservation_id
              AND r.reservation_state = 'TERMINAL_RECORDED'
              AND a.state IN ('TERMINAL_RECORDED', 'SUCCESS_SELECTED', 'CLOSED')
              AND s.state = 'CLOSED'
        ))
)
BEGIN
    SELECT RAISE(ABORT, 'execution phase requires its durable projection fact');
END;

CREATE TRIGGER launch_executions_before_insert
BEFORE INSERT ON launch_executions
FOR EACH ROW
BEGIN
    SELECT CASE WHEN sha256(NEW.process_creation_json)
        IS NOT NEW.process_creation_digest
        THEN RAISE(ABORT, 'process creation evidence digest is invalid') END;
    SELECT CASE WHEN sha256(NEW.job_object_json) IS NOT NEW.job_object_digest
        THEN RAISE(ABORT, 'job object evidence digest is invalid') END;
    SELECT CASE WHEN sha256(NEW.resume_authorization_json)
        IS NOT NEW.resume_authorization_digest
        THEN RAISE(ABORT, 'resume authorization evidence digest is invalid') END;
    SELECT CASE WHEN NOT (
        NEW.phase = 'PRE_RESUME_READY'
        AND NEW.resume_intent_json IS NULL
        AND NEW.resume_intent_digest IS NULL
        AND NEW.resume_intent_committed_at_utc IS NULL
        AND NEW.post_resume_json IS NULL
        AND NEW.post_resume_digest IS NULL
        AND NEW.cleanup_json IS NULL
        AND NEW.cleanup_digest IS NULL
    ) THEN RAISE(ABORT, 'launch execution must begin pre-resume without post evidence') END;
END;

CREATE TRIGGER launch_executions_parent_policy_before_insert
BEFORE INSERT ON launch_executions
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE r.launch_reservation_id = NEW.launch_reservation_id
          AND r.application_release_version IS NEW.application_release_version
          AND r.authority_policy_version IS NEW.authority_policy_version
          AND r.reservation_state = 'PROCESS_INTENT_COMMITTED'
          AND r.process_intent_json IS NOT NULL
          AND r.process_intent_digest IS NOT NULL
          AND r.process_intent_committed_at_utc IS NOT NULL
          AND sha256(r.process_intent_json) IS r.process_intent_digest
          AND NEW.created_at_utc >= r.process_intent_committed_at_utc
          AND c.state = 'COMMITTED'
          AND a.state = 'LAUNCH_RESERVED'
          AND s.state = 'OPEN'
          AND NOT EXISTS (
              SELECT 1 FROM terminals t
              WHERE t.launch_reservation_id = r.launch_reservation_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
          )
    ) THEN RAISE(ABORT, 'execution policy binding differs from reservation') END;
END;

CREATE TRIGGER launch_executions_no_delete
BEFORE DELETE ON launch_executions
BEGIN
    SELECT RAISE(ABORT, 'launch executions cannot be deleted');
END;

CREATE TRIGGER launch_executions_resume_intent_append_only
BEFORE UPDATE ON launch_executions
WHEN OLD.resume_intent_json IS NOT NEW.resume_intent_json
  OR OLD.resume_intent_digest IS NOT NEW.resume_intent_digest
  OR OLD.resume_intent_committed_at_utc IS NOT NEW.resume_intent_committed_at_utc
BEGIN
    SELECT CASE WHEN NOT (
        OLD.resume_intent_json IS NULL
        AND OLD.resume_intent_digest IS NULL
        AND OLD.resume_intent_committed_at_utc IS NULL
        AND NEW.resume_intent_json IS NOT NULL
        AND NEW.resume_intent_digest IS NOT NULL
        AND NEW.resume_intent_committed_at_utc IS NOT NULL
        AND NEW.resume_intent_committed_at_utc >= OLD.created_at_utc
        AND sha256(NEW.resume_intent_json) IS NEW.resume_intent_digest
        AND CAST(NEW.resume_intent_json AS TEXT) =
            '{"execution_id":"' || NEW.launch_execution_id ||
            '","resume_operation":"ResumeThread","schema":1}'
        AND OLD.phase = 'PRE_RESUME_READY'
        AND NEW.phase = 'RESUME_INTENT_COMMITTED'
    ) THEN RAISE(ABORT, 'resume intent is append-only') END;
END;

CREATE TRIGGER launch_executions_post_resume_append_only
BEFORE UPDATE ON launch_executions
WHEN OLD.post_resume_json IS NOT NEW.post_resume_json
  OR OLD.post_resume_digest IS NOT NEW.post_resume_digest
BEGIN
    SELECT CASE WHEN NOT (
        OLD.post_resume_json IS NULL
        AND OLD.post_resume_digest IS NULL
        AND NEW.post_resume_json IS NOT NULL
        AND NEW.post_resume_digest IS NOT NULL
        AND sha256(NEW.post_resume_json) IS NEW.post_resume_digest
        AND CAST(NEW.post_resume_json AS TEXT) =
            '{"execution_id":"' || NEW.launch_execution_id ||
            '","resume_intent_digest":"' || lower(hex(NEW.resume_intent_digest)) ||
            '","resume_result":"RESUMED","schema":1}'
        AND OLD.phase = 'RESUME_INTENT_COMMITTED'
        AND NEW.phase = 'RESUME_RECORDED'
    ) THEN RAISE(ABORT, 'post-resume evidence is append-only') END;
END;

CREATE TRIGGER launch_executions_cleanup_append_only
BEFORE UPDATE ON launch_executions
WHEN OLD.cleanup_json IS NOT NEW.cleanup_json
  OR OLD.cleanup_digest IS NOT NEW.cleanup_digest
BEGIN
    SELECT CASE WHEN NOT (
        OLD.cleanup_json IS NULL
        AND OLD.cleanup_digest IS NULL
        AND NEW.cleanup_json IS NOT NULL
        AND NEW.cleanup_digest IS NOT NULL
        AND sha256(NEW.cleanup_json) IS NEW.cleanup_digest
        AND OLD.phase = 'RESUME_INTENT_COMMITTED'
        AND NEW.phase = 'RESUME_RECORDED'
    ) THEN RAISE(ABORT, 'cleanup evidence is append-only') END;
END;

CREATE TRIGGER terminals_no_update
BEFORE UPDATE ON terminals
BEGIN
    SELECT RAISE(ABORT, 'terminals are immutable');
END;

CREATE TRIGGER terminals_before_insert
BEFORE INSERT ON terminals
FOR EACH ROW
BEGIN
    SELECT CASE WHEN sha256(NEW.evidence_json) IS NOT NEW.evidence_digest
        THEN RAISE(ABORT, 'terminal evidence digest is invalid') END;
    SELECT CASE WHEN sha256(NEW.sanitized_diagnostics_json)
        IS NOT NEW.sanitized_diagnostics_digest
        THEN RAISE(ABORT, 'terminal diagnostics digest is invalid') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE r.launch_reservation_id = NEW.launch_reservation_id
          AND r.request_digest IS NEW.request_digest
          AND c.state = 'COMMITTED'
          AND a.state IN ('LAUNCH_RESERVED', 'LAUNCH_MAY_HAVE_OCCURRED')
          AND s.state = 'OPEN'
          AND NOT EXISTS (
              SELECT 1 FROM session_selections ss
              WHERE ss.session_id = s.session_id
          )
    ) THEN RAISE(ABORT, 'terminal request binding differs from reservation') END;

    SELECT CASE WHEN NEW.terminal_state = 'FAILED'
        AND NEW.provider_call_disposition = 'NOT_STARTED'
        AND NOT EXISTS (
            SELECT 1 FROM launch_reservations r
            WHERE r.launch_reservation_id = NEW.launch_reservation_id
              AND r.outcome_recorded_at_utc IS NOT NULL
              AND NEW.recorded_at_utc >= r.outcome_recorded_at_utc
        )
        THEN RAISE(ABORT, 'terminal timestamp predates process failure') END;
    SELECT CASE WHEN (
        NEW.terminal_state IN ('SUCCEEDED', 'AMBIGUOUS')
        OR (NEW.terminal_state = 'FAILED'
            AND NEW.provider_call_disposition = 'CONFIRMED')
    ) AND NOT EXISTS (
        SELECT 1 FROM launch_executions e
        WHERE e.launch_reservation_id = NEW.launch_reservation_id
          AND e.resume_intent_committed_at_utc IS NOT NULL
          AND NEW.recorded_at_utc >= e.resume_intent_committed_at_utc
    ) THEN RAISE(ABORT, 'terminal timestamp predates resumed execution') END;
    SELECT CASE WHEN NEW.terminal_state = 'AMBIGUOUS' AND EXISTS (
        SELECT 1
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        WHERE r.launch_reservation_id = NEW.launch_reservation_id
          AND a.state = 'LAUNCH_MAY_HAVE_OCCURRED'
    ) AND NOT EXISTS (
        SELECT 1
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN manual_recoveries mr ON mr.session_id = a.session_id
        WHERE r.launch_reservation_id = NEW.launch_reservation_id
          AND (
              (mr.target_kind = 'ATTEMPT' AND mr.target_id = a.attempt_id)
              OR (mr.target_kind = 'CLAIM' AND mr.target_id = c.claim_id)
          )
          AND mr.action IN (
              'RECORD_ATTEMPT_AMBIGUITY', 'RECORD_CLAIM_AMBIGUITY'
          )
          AND NEW.recorded_at_utc >= mr.created_at_utc
    ) THEN RAISE(ABORT, 'terminal timestamp predates ambiguity recovery') END;
    SELECT CASE WHEN NEW.terminal_state = 'CLOSED' AND NOT EXISTS (
        SELECT 1
        FROM manual_recoveries mr
        WHERE mr.target_kind = 'LAUNCH_RESERVATION'
          AND mr.target_id = NEW.launch_reservation_id
          AND mr.action IN (
              'CLASSIFY_LAUNCH_RESERVATION',
              'CLASSIFY_PROCESS_OUTCOME_UNKNOWN',
              'CLASSIFY_PRE_RESUME_READY',
              'CLASSIFY_RESUME_OUTCOME_UNKNOWN'
          )
          AND NEW.recorded_at_utc >= mr.created_at_utc
    ) THEN RAISE(ABORT, 'terminal timestamp predates reservation recovery') END;

    SELECT CASE WHEN NEW.terminal_state = 'SUCCEEDED' AND NOT EXISTS (
        SELECT 1
        FROM launch_executions e
        WHERE e.launch_reservation_id = NEW.launch_reservation_id
          AND e.phase = 'RESUME_RECORDED'
          AND e.post_resume_json IS NOT NULL
          AND e.post_resume_digest IS NOT NULL
          AND e.cleanup_json IS NOT NULL
          AND e.cleanup_digest IS NOT NULL
    ) THEN RAISE(ABORT, 'successful terminal requires resumed execution evidence') END;
    SELECT CASE WHEN NEW.terminal_state = 'SUCCEEDED'
        AND (NEW.provider_call_disposition <> 'CONFIRMED' OR NEW.snapshot_digest IS NULL)
        THEN RAISE(ABORT, 'successful terminal matrix entry is invalid') END;
    SELECT CASE WHEN NEW.terminal_state = 'AMBIGUOUS'
        AND (NEW.provider_call_disposition <> 'MAY_HAVE_OCCURRED' OR NEW.snapshot_digest IS NOT NULL)
        THEN RAISE(ABORT, 'ambiguous terminal matrix entry is invalid') END;
    SELECT CASE WHEN NEW.terminal_state = 'AMBIGUOUS' AND NOT EXISTS (
        SELECT 1
        FROM launch_executions e
        WHERE e.launch_reservation_id = NEW.launch_reservation_id
          AND e.phase IN ('RESUME_RECORDED', 'POST_RESUME_AMBIGUOUS')
          AND e.post_resume_json IS NOT NULL
          AND e.post_resume_digest IS NOT NULL
          AND e.cleanup_json IS NOT NULL
          AND e.cleanup_digest IS NOT NULL
    ) THEN RAISE(ABORT, 'ambiguous terminal requires resume evidence') END;
    SELECT CASE WHEN NEW.terminal_state = 'FAILED' AND NOT (
        (NEW.provider_call_disposition = 'NOT_STARTED'
         AND NEW.snapshot_digest IS NULL
         AND EXISTS (
             SELECT 1 FROM launch_reservations r
             WHERE r.launch_reservation_id = NEW.launch_reservation_id
               AND r.reservation_state = 'PROCESS_CREATION_FAILED'
               AND r.process_intent_json IS NOT NULL
               AND r.process_intent_digest IS NOT NULL
               AND sha256(r.process_intent_json) IS r.process_intent_digest
               AND r.process_creation_failure_json IS NOT NULL
               AND r.process_creation_failure_digest IS NOT NULL
         ))
        OR (NEW.provider_call_disposition = 'CONFIRMED'
            AND NEW.snapshot_digest IS NULL
            AND EXISTS (
                SELECT 1 FROM launch_executions e
                WHERE e.launch_reservation_id = NEW.launch_reservation_id
                  AND e.phase = 'RESUME_RECORDED'
                  AND e.post_resume_json IS NOT NULL
                  AND e.cleanup_json IS NOT NULL
            ))
    ) THEN RAISE(ABORT, 'failed terminal matrix entry is invalid') END;
    SELECT CASE WHEN NEW.terminal_state = 'CLOSED' AND NOT (
        NEW.provider_call_disposition = 'MAY_HAVE_OCCURRED'
        AND NEW.snapshot_digest IS NULL
        AND EXISTS (
            SELECT 1 FROM launch_reservations r
            WHERE r.launch_reservation_id = NEW.launch_reservation_id
              AND r.reservation_state = 'MANUAL_REVIEW'
        )
    ) THEN RAISE(ABORT, 'closed terminal matrix entry is invalid') END;
END;

CREATE TRIGGER terminals_no_delete
BEFORE DELETE ON terminals
BEGIN
    SELECT RAISE(ABORT, 'terminals cannot be deleted');
END;

CREATE TRIGGER session_selections_before_insert
BEFORE INSERT ON session_selections
FOR EACH ROW
BEGIN
    SELECT CASE WHEN sha256(NEW.selection_evidence_json)
        IS NOT NEW.selection_evidence_digest
        THEN RAISE(ABORT, 'selection evidence digest is invalid') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM sessions
        WHERE session_id = NEW.session_id AND state = 'OPEN'
    ) THEN RAISE(ABORT, 'selection session is not open') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM terminals t
        JOIN launch_reservations r ON r.launch_reservation_id = t.launch_reservation_id
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        WHERE t.terminal_id = NEW.terminal_id
          AND a.session_id = NEW.session_id
          AND a.state = 'TERMINAL_RECORDED'
          AND r.reservation_state = 'TERMINAL_RECORDED'
          AND t.terminal_state = 'SUCCEEDED'
          AND t.provider_call_disposition = 'CONFIRMED'
          AND t.snapshot_digest IS NEW.snapshot_digest
          AND NEW.selected_at_utc >= t.recorded_at_utc
    ) THEN RAISE(ABORT, 'selection terminal does not belong to the session') END;
END;

CREATE TRIGGER session_selections_no_update
BEFORE UPDATE ON session_selections
BEGIN
    SELECT RAISE(ABORT, 'session selections are immutable');
END;

CREATE TRIGGER session_selections_no_delete
BEFORE DELETE ON session_selections
BEGIN
    SELECT RAISE(ABORT, 'session selections cannot be deleted');
END;

CREATE TRIGGER manual_recoveries_before_insert
BEFORE INSERT ON manual_recoveries
FOR EACH ROW
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM sessions
        WHERE session_id = NEW.session_id AND state = 'OPEN'
    ) THEN RAISE(ABORT, 'recovery session is not eligible') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM session_selections
        WHERE session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'recovery action matrix entry is invalid') END;
    SELECT CASE WHEN NEW.recovery_ordinal <> (
        SELECT next_recovery_ordinal FROM sessions WHERE session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'recovery ordinal is not the session counter') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM manual_recoveries
        WHERE session_id = NEW.session_id
          AND target_kind = NEW.target_kind
          AND target_id = NEW.target_id
          AND action = NEW.action
    ) THEN RAISE(ABORT, 'recovery action already recorded for target') END;
    SELECT CASE WHEN NEW.target_kind = 'SESSION' AND NOT EXISTS (
        SELECT 1 FROM sessions
        WHERE session_id = NEW.target_id AND session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'recovery session target binding is invalid') END;
    SELECT CASE WHEN NEW.target_kind = 'ATTEMPT' AND NOT EXISTS (
        SELECT 1 FROM attempts
        WHERE attempt_id = NEW.target_id
          AND session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'recovery attempt target binding is invalid') END;
    SELECT CASE WHEN NEW.target_kind = 'CLAIM' AND NOT EXISTS (
        SELECT 1
        FROM provider_call_claims c
        JOIN attempts a ON a.attempt_id = c.attempt_id
        WHERE c.claim_id = NEW.target_id AND a.session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'recovery claim target binding is invalid') END;
    SELECT CASE WHEN NEW.target_kind = 'LAUNCH_RESERVATION' AND NOT EXISTS (
        SELECT 1
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        WHERE r.launch_reservation_id = NEW.target_id AND a.session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'recovery reservation target binding is invalid') END;
    SELECT CASE WHEN NEW.target_kind = 'TERMINAL' AND NOT EXISTS (
        SELECT 1
        FROM terminals t
        JOIN launch_reservations r ON r.launch_reservation_id = t.launch_reservation_id
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        WHERE t.terminal_id = NEW.target_id AND a.session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'recovery terminal target binding is invalid') END;
    SELECT CASE WHEN sha256(NEW.operator_evidence_json) IS NOT NEW.operator_evidence_digest
        THEN RAISE(ABORT, 'recovery operator evidence digest is invalid') END;
    SELECT CASE WHEN NOT (
        NEW.recovery_schema = 1
        AND NEW.recovery_policy_version = 'recovery-policy/v1'
    ) THEN RAISE(ABORT, 'recovery schema or policy is invalid') END;

    SELECT CASE WHEN NOT (
        (NEW.action = 'RECORD_ATTEMPT_AMBIGUITY'
         AND EXISTS (
             SELECT 1
             FROM attempts a
             JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
             JOIN launch_reservations r ON r.claim_id = c.claim_id
             JOIN launch_executions e
               ON e.launch_reservation_id = r.launch_reservation_id
             WHERE a.attempt_id = NEW.target_id
               AND a.session_id = NEW.session_id
               AND e.resume_intent_committed_at_utc IS NOT NULL
               AND NEW.created_at_utc >= e.resume_intent_committed_at_utc
         ))
        OR (NEW.action = 'RECORD_CLAIM_AMBIGUITY'
            AND EXISTS (
                SELECT 1
                FROM provider_call_claims c
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN launch_reservations r ON r.claim_id = c.claim_id
                JOIN launch_executions e
                  ON e.launch_reservation_id = r.launch_reservation_id
                WHERE c.claim_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND e.resume_intent_committed_at_utc IS NOT NULL
                  AND NEW.created_at_utc >= e.resume_intent_committed_at_utc
            ))
        OR (NEW.action = 'CLASSIFY_LAUNCH_RESERVATION'
            AND EXISTS (
                SELECT 1 FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                WHERE r.launch_reservation_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND NEW.created_at_utc >= r.committed_at_utc
            ))
        OR (NEW.action = 'CLASSIFY_PROCESS_OUTCOME_UNKNOWN'
            AND EXISTS (
                SELECT 1 FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                WHERE r.launch_reservation_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND r.process_intent_committed_at_utc IS NOT NULL
                  AND NEW.created_at_utc >= r.process_intent_committed_at_utc
            ))
        OR (NEW.action = 'CLASSIFY_PRE_RESUME_READY'
            AND EXISTS (
                SELECT 1 FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN launch_executions e
                  ON e.launch_reservation_id = r.launch_reservation_id
                WHERE r.launch_reservation_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND NEW.created_at_utc >= e.created_at_utc
            ))
        OR (NEW.action = 'CLASSIFY_RESUME_OUTCOME_UNKNOWN'
            AND EXISTS (
                SELECT 1 FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN launch_executions e
                  ON e.launch_reservation_id = r.launch_reservation_id
                WHERE r.launch_reservation_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND e.resume_intent_committed_at_utc IS NOT NULL
                  AND NEW.created_at_utc >= e.resume_intent_committed_at_utc
            ))
        OR (NEW.action = 'SELECT_COMMITTED_SUCCESS'
            AND EXISTS (
                SELECT 1 FROM terminals t
                JOIN launch_reservations r
                  ON r.launch_reservation_id = t.launch_reservation_id
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                WHERE t.terminal_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND NEW.created_at_utc >= t.recorded_at_utc
            ))
        OR (NEW.action = 'CLOSE_SESSION'
            AND EXISTS (
                SELECT 1 FROM sessions s
                WHERE s.session_id = NEW.target_id
                  AND s.session_id = NEW.session_id
                  AND NEW.created_at_utc >= s.created_at_utc
            )
            AND NOT EXISTS (
                SELECT 1
                FROM terminals t
                JOIN launch_reservations r
                  ON r.launch_reservation_id = t.launch_reservation_id
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                WHERE a.session_id = NEW.session_id
                  AND t.recorded_at_utc > NEW.created_at_utc
            ))
        OR (NEW.action = 'ACKNOWLEDGE_RESTORE'
            AND EXISTS (
                SELECT 1 FROM sessions s
                WHERE s.session_id = NEW.target_id
                  AND s.session_id = NEW.session_id
                  AND NEW.created_at_utc >= s.created_at_utc
            ))
    ) THEN RAISE(ABORT, 'recovery timestamp predates its durable predecessor') END;

    SELECT CASE WHEN NOT (
        (NEW.action = 'RECORD_ATTEMPT_AMBIGUITY'
         AND NEW.target_kind = 'ATTEMPT'
         AND NEW.predecessor_state = 'LAUNCH_RESERVED'
         AND NEW.resulting_state = 'AMBIGUITY_RECORDED'
         AND EXISTS (
             SELECT 1
             FROM attempts a
             JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
             JOIN launch_reservations r ON r.claim_id = c.claim_id
             JOIN launch_executions e ON e.launch_reservation_id = r.launch_reservation_id
             JOIN sessions s ON s.session_id = a.session_id
             WHERE a.attempt_id = NEW.target_id
               AND a.session_id = NEW.session_id
               AND a.state = 'LAUNCH_RESERVED'
               AND c.state = 'COMMITTED'
               AND r.reservation_state = 'PROCESS_CREATED'
               AND e.phase = 'RESUME_RECORDED'
               AND e.post_resume_json IS NOT NULL
               AND e.post_resume_digest IS NOT NULL
               AND sha256(e.post_resume_json) IS e.post_resume_digest
               AND e.cleanup_json IS NOT NULL
               AND e.cleanup_digest IS NOT NULL
               AND sha256(e.cleanup_json) IS e.cleanup_digest
               AND s.state = 'OPEN'
               AND NOT EXISTS (
                   SELECT 1 FROM terminals t
                   WHERE t.launch_reservation_id = r.launch_reservation_id
               )
         ))
        OR (NEW.action = 'RECORD_CLAIM_AMBIGUITY'
            AND NEW.target_kind = 'CLAIM'
            AND NEW.predecessor_state = 'COMMITTED'
            AND NEW.resulting_state = 'AMBIGUITY_RECORDED'
            AND EXISTS (
                SELECT 1
                FROM provider_call_claims c
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN launch_reservations r ON r.claim_id = c.claim_id
                JOIN launch_executions e ON e.launch_reservation_id = r.launch_reservation_id
                JOIN sessions s ON s.session_id = a.session_id
                WHERE c.claim_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND c.state = 'COMMITTED'
                  AND a.state = 'LAUNCH_RESERVED'
                  AND r.reservation_state = 'PROCESS_CREATED'
                  AND e.phase = 'RESUME_RECORDED'
                  AND e.post_resume_json IS NOT NULL
                  AND e.post_resume_digest IS NOT NULL
                  AND sha256(e.post_resume_json) IS e.post_resume_digest
                  AND e.cleanup_json IS NOT NULL
                  AND e.cleanup_digest IS NOT NULL
                  AND sha256(e.cleanup_json) IS e.cleanup_digest
                  AND s.state = 'OPEN'
                  AND NOT EXISTS (
                      SELECT 1 FROM terminals t
                      WHERE t.launch_reservation_id = r.launch_reservation_id
                  )
            ))
        OR (NEW.action = 'CLASSIFY_LAUNCH_RESERVATION'
            AND NEW.target_kind = 'LAUNCH_RESERVATION'
            AND NEW.predecessor_state = 'COMMITTED'
            AND NEW.resulting_state = 'MANUAL_REVIEW'
            AND EXISTS (
                SELECT 1
                FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN sessions s ON s.session_id = a.session_id
                WHERE r.launch_reservation_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND r.reservation_state = 'COMMITTED'
                  AND c.state = 'COMMITTED'
                  AND a.state = 'LAUNCH_RESERVED'
                  AND s.state = 'OPEN'
                  AND NOT EXISTS (
                      SELECT 1 FROM launch_executions e
                      WHERE e.launch_reservation_id = r.launch_reservation_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM terminals t
                      WHERE t.launch_reservation_id = r.launch_reservation_id
                  )
            ))
        OR (NEW.action = 'CLASSIFY_PROCESS_OUTCOME_UNKNOWN'
            AND NEW.target_kind = 'LAUNCH_RESERVATION'
            AND NEW.predecessor_state = 'PROCESS_INTENT_COMMITTED'
            AND NEW.resulting_state = 'MANUAL_REVIEW'
            AND EXISTS (
                SELECT 1
                FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN sessions s ON s.session_id = a.session_id
                WHERE r.launch_reservation_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND r.reservation_state = 'PROCESS_INTENT_COMMITTED'
                  AND c.state = 'COMMITTED'
                  AND a.state = 'LAUNCH_RESERVED'
                  AND s.state = 'OPEN'
                  AND r.process_intent_json IS NOT NULL
                  AND r.process_intent_digest IS NOT NULL
                  AND r.process_intent_committed_at_utc IS NOT NULL
                  AND sha256(r.process_intent_json) IS r.process_intent_digest
                  AND r.process_creation_failure_json IS NULL
                  AND r.process_creation_failure_digest IS NULL
            )
            AND NOT EXISTS (
                SELECT 1 FROM launch_executions e
                WHERE e.launch_reservation_id = NEW.target_id
            ))
        OR (NEW.action = 'CLASSIFY_PRE_RESUME_READY'
            AND NEW.target_kind = 'LAUNCH_RESERVATION'
            AND NEW.predecessor_state = 'PROCESS_CREATED'
            AND NEW.resulting_state = 'MANUAL_REVIEW'
            AND EXISTS (
                SELECT 1
                FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN sessions s ON s.session_id = a.session_id
                WHERE r.launch_reservation_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND r.reservation_state = 'PROCESS_CREATED'
                  AND c.state = 'COMMITTED'
                  AND a.state = 'LAUNCH_RESERVED'
                  AND s.state = 'OPEN'
                  AND NOT EXISTS (
                      SELECT 1 FROM terminals t
                      WHERE t.launch_reservation_id = r.launch_reservation_id
                  )
            )
            AND (SELECT count(*) FROM launch_executions e
                 WHERE e.launch_reservation_id = NEW.target_id) = 1
            AND EXISTS (
                SELECT 1 FROM launch_executions e
                WHERE e.launch_reservation_id = NEW.target_id
                  AND e.phase = 'PRE_RESUME_READY'
                  AND sha256(e.process_creation_json) IS e.process_creation_digest
                  AND sha256(e.job_object_json) IS e.job_object_digest
                  AND sha256(e.resume_authorization_json) IS e.resume_authorization_digest
                  AND e.resume_intent_json IS NULL
                  AND e.resume_intent_digest IS NULL
                  AND e.resume_intent_committed_at_utc IS NULL
                  AND e.post_resume_json IS NULL
                  AND e.post_resume_digest IS NULL
                  AND e.cleanup_json IS NULL
                  AND e.cleanup_digest IS NULL
            ))
        OR (NEW.action = 'CLASSIFY_RESUME_OUTCOME_UNKNOWN'
            AND NEW.target_kind = 'LAUNCH_RESERVATION'
            AND NEW.predecessor_state = 'PROCESS_CREATED'
            AND NEW.resulting_state = 'MANUAL_REVIEW'
            AND EXISTS (
                SELECT 1
                FROM launch_reservations r
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN sessions s ON s.session_id = a.session_id
                WHERE r.launch_reservation_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND r.reservation_state = 'PROCESS_CREATED'
                  AND c.state = 'COMMITTED'
                  AND a.state = 'LAUNCH_RESERVED'
                  AND s.state = 'OPEN'
                  AND NOT EXISTS (
                      SELECT 1 FROM terminals t
                      WHERE t.launch_reservation_id = r.launch_reservation_id
                  )
            )
            AND (SELECT count(*) FROM launch_executions e
                 WHERE e.launch_reservation_id = NEW.target_id) = 1
            AND EXISTS (
                SELECT 1
                FROM launch_executions e
                WHERE e.launch_reservation_id = NEW.target_id
                  AND e.phase = 'RESUME_INTENT_COMMITTED'
                  AND e.process_creation_json IS NOT NULL
                  AND e.process_creation_digest IS NOT NULL
                  AND sha256(e.process_creation_json) IS e.process_creation_digest
                  AND e.job_object_json IS NOT NULL
                  AND e.job_object_digest IS NOT NULL
                  AND sha256(e.job_object_json) IS e.job_object_digest
                  AND e.resume_authorization_json IS NOT NULL
                  AND e.resume_authorization_digest IS NOT NULL
                  AND sha256(e.resume_authorization_json) IS e.resume_authorization_digest
                  AND e.resume_intent_json IS NOT NULL
                  AND e.resume_intent_digest IS NOT NULL
                  AND sha256(e.resume_intent_json) IS e.resume_intent_digest
                  AND e.resume_intent_committed_at_utc IS NOT NULL
                  AND e.post_resume_json IS NULL
                  AND e.post_resume_digest IS NULL
                  AND e.cleanup_json IS NULL
                  AND e.cleanup_digest IS NULL
            ))
        OR (NEW.action = 'SELECT_COMMITTED_SUCCESS'
            AND NEW.target_kind = 'TERMINAL'
            AND NEW.predecessor_state = 'SUCCEEDED'
            AND NEW.resulting_state = 'SUCCESS_SELECTED'
            AND EXISTS (
                SELECT 1
                FROM terminals t
                JOIN launch_reservations r
                  ON r.launch_reservation_id = t.launch_reservation_id
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                JOIN sessions s ON s.session_id = a.session_id
                WHERE t.terminal_id = NEW.target_id
                  AND a.session_id = NEW.session_id
                  AND t.terminal_state = 'SUCCEEDED'
                  AND t.provider_call_disposition = 'CONFIRMED'
                  AND t.snapshot_digest IS NOT NULL
                  AND r.reservation_state = 'TERMINAL_RECORDED'
                  AND c.state = 'COMMITTED'
                  AND a.state = 'TERMINAL_RECORDED'
                  AND s.state = 'OPEN'
            ))
        OR (NEW.action = 'CLOSE_SESSION'
            AND NEW.target_kind = 'SESSION'
            AND NEW.predecessor_state = 'OPEN'
            AND NEW.resulting_state = 'CLOSED'
            AND NOT EXISTS (
                SELECT 1 FROM attempts
                WHERE session_id = NEW.target_id
                  AND state NOT IN ('TERMINAL_RECORDED', 'SUCCESS_SELECTED', 'CLOSED')
            )
            AND NOT EXISTS (
                SELECT 1
                FROM attempts a
                WHERE a.session_id = NEW.target_id
                  AND a.state = 'TERMINAL_RECORDED'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM provider_call_claims c
                      JOIN launch_reservations r ON r.claim_id = c.claim_id
                      JOIN terminals t
                        ON t.launch_reservation_id = r.launch_reservation_id
                      WHERE c.attempt_id = a.attempt_id
                        AND c.state = 'COMMITTED'
                        AND r.reservation_state = 'TERMINAL_RECORDED'
                  )
            )
            AND NOT EXISTS (
                SELECT 1
                FROM attempts a
                WHERE a.session_id = NEW.target_id
                  AND a.state = 'SUCCESS_SELECTED'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM provider_call_claims c
                      JOIN launch_reservations r ON r.claim_id = c.claim_id
                      JOIN terminals t
                        ON t.launch_reservation_id = r.launch_reservation_id
                      JOIN session_selections ss
                        ON ss.terminal_id = t.terminal_id
                      WHERE c.attempt_id = a.attempt_id
                        AND c.state = 'COMMITTED'
                        AND r.reservation_state = 'TERMINAL_RECORDED'
                        AND ss.session_id = NEW.target_id
                  )
            )
            AND NOT EXISTS (
                SELECT 1
                FROM attempts a
                WHERE a.session_id = NEW.target_id
                  AND a.state = 'CLOSED'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM provider_call_claims c
                      JOIN launch_reservations r ON r.claim_id = c.claim_id
                      JOIN terminals t
                        ON t.launch_reservation_id = r.launch_reservation_id
                      WHERE c.attempt_id = a.attempt_id
                        AND c.state = 'COMMITTED'
                        AND r.reservation_state = 'TERMINAL_RECORDED'
                  )
            )
            AND NOT EXISTS (
                SELECT 1
                FROM terminals t
                JOIN launch_reservations r ON r.launch_reservation_id = t.launch_reservation_id
                JOIN provider_call_claims c ON c.claim_id = r.claim_id
                JOIN attempts a ON a.attempt_id = c.attempt_id
                WHERE a.session_id = NEW.target_id
                  AND t.terminal_state = 'AMBIGUOUS'
            ))
        OR (NEW.action = 'ACKNOWLEDGE_RESTORE'
            AND NEW.target_kind = 'SESSION'
            AND NEW.predecessor_state = 'OPEN'
            AND NEW.resulting_state = 'RESTORE_ACKNOWLEDGED')
    ) THEN RAISE(ABORT, 'recovery action matrix entry is invalid') END;
END;

CREATE TRIGGER manual_recoveries_after_insert
AFTER INSERT ON manual_recoveries
FOR EACH ROW
BEGIN
    UPDATE sessions
    SET next_recovery_ordinal = next_recovery_ordinal + 1
    WHERE session_id = NEW.session_id
      AND next_recovery_ordinal = NEW.recovery_ordinal;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM sessions
        WHERE session_id = NEW.session_id
          AND next_recovery_ordinal = NEW.recovery_ordinal + 1
    ) THEN RAISE(ABORT, 'recovery counter was not incremented exactly once') END;
END;

CREATE TRIGGER manual_recoveries_no_update
BEFORE UPDATE ON manual_recoveries
BEGIN
    SELECT RAISE(ABORT, 'manual recoveries are immutable');
END;

CREATE TRIGGER manual_recoveries_no_delete
BEFORE DELETE ON manual_recoveries
BEGIN
    SELECT RAISE(ABORT, 'manual recoveries cannot be deleted');
END;
