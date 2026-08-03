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
    created_at_utc TEXT NOT NULL,
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
    applied_at_utc TEXT NOT NULL,
    UNIQUE (authority_epoch_id, schema_version)
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    authority_epoch_id TEXT NOT NULL REFERENCES authority_metadata(authority_epoch_id),
    session_schema INTEGER NOT NULL CHECK (session_schema > 0),
    authority_policy_version TEXT NOT NULL,
    claim_policy_version TEXT NOT NULL,
    target_session_date TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('OPEN', 'SUCCESS_SELECTED', 'CLOSED')),
    next_attempt_ordinal INTEGER NOT NULL CHECK (next_attempt_ordinal >= 0),
    next_recovery_ordinal INTEGER NOT NULL CHECK (next_recovery_ordinal >= 0),
    request_json BLOB NOT NULL,
    request_digest BLOB NOT NULL CHECK (length(request_digest) = 32),
    created_at_utc TEXT NOT NULL,
    closed_at_utc TEXT,
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
    attempt_schema INTEGER NOT NULL CHECK (attempt_schema > 0),
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
    created_at_utc TEXT NOT NULL,
    UNIQUE (session_id, ordinal)
);

CREATE TABLE provider_call_claims (
    claim_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(attempt_id),
    claim_schema INTEGER NOT NULL CHECK (claim_schema > 0),
    claim_policy_version TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    permitted_provider_operation TEXT NOT NULL,
    provider_call_budget INTEGER NOT NULL CHECK (provider_call_budget = 1),
    request_json BLOB NOT NULL,
    request_digest BLOB NOT NULL CHECK (length(request_digest) = 32),
    claim_evidence_json BLOB NOT NULL,
    claim_evidence_digest BLOB NOT NULL CHECK (length(claim_evidence_digest) = 32),
    state TEXT NOT NULL CHECK (state = 'COMMITTED'),
    committed_at_utc TEXT NOT NULL
);

CREATE TABLE launch_reservations (
    launch_reservation_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL UNIQUE REFERENCES provider_call_claims(claim_id),
    launch_reservation_schema INTEGER NOT NULL CHECK (launch_reservation_schema > 0),
    application_release_version TEXT NOT NULL,
    authority_policy_version TEXT NOT NULL,
    claim_policy_version TEXT NOT NULL,
    request_digest BLOB NOT NULL CHECK (length(request_digest) = 32),
    reservation_evidence_json BLOB NOT NULL,
    reservation_evidence_digest BLOB NOT NULL CHECK (length(reservation_evidence_digest) = 32),
    reservation_state TEXT NOT NULL CHECK (reservation_state IN (
        'COMMITTED', 'PROCESS_CREATED', 'PROCESS_CREATION_FAILED',
        'MANUAL_REVIEW', 'TERMINAL_RECORDED'
    )),
    process_creation_failure_json BLOB,
    process_creation_failure_digest BLOB,
    committed_at_utc TEXT NOT NULL,
    outcome_recorded_at_utc TEXT,
    CHECK ((process_creation_failure_json IS NULL) = (process_creation_failure_digest IS NULL)),
    CHECK (
        process_creation_failure_digest IS NULL
        OR length(process_creation_failure_digest) = 32
    )
);

CREATE TABLE launch_executions (
    launch_execution_id TEXT PRIMARY KEY,
    launch_reservation_id TEXT NOT NULL UNIQUE REFERENCES launch_reservations(launch_reservation_id),
    launch_schema INTEGER NOT NULL CHECK (launch_schema > 0),
    application_release_version TEXT NOT NULL,
    authority_policy_version TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN (
        'PRE_RESUME_READY', 'RESUME_RECORDED', 'POST_RESUME_AMBIGUOUS',
        'TERMINAL_RECORDED', 'CLOSED'
    )),
    process_creation_json BLOB NOT NULL,
    process_creation_digest BLOB NOT NULL CHECK (length(process_creation_digest) = 32),
    job_object_json BLOB NOT NULL,
    job_object_digest BLOB NOT NULL CHECK (length(job_object_digest) = 32),
    resume_authorization_json BLOB NOT NULL,
    resume_authorization_digest BLOB NOT NULL CHECK (length(resume_authorization_digest) = 32),
    post_resume_json BLOB,
    post_resume_digest BLOB,
    cleanup_json BLOB,
    cleanup_digest BLOB,
    created_at_utc TEXT NOT NULL,
    CHECK (post_resume_digest IS NULL OR length(post_resume_digest) = 32),
    CHECK (cleanup_digest IS NULL OR length(cleanup_digest) = 32),
    CHECK ((post_resume_json IS NULL) = (post_resume_digest IS NULL)),
    CHECK ((cleanup_json IS NULL) = (cleanup_digest IS NULL))
);

CREATE TABLE terminals (
    terminal_id TEXT PRIMARY KEY,
    launch_reservation_id TEXT NOT NULL UNIQUE REFERENCES launch_reservations(launch_reservation_id),
    terminal_schema INTEGER NOT NULL CHECK (terminal_schema > 0),
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
    recorded_at_utc TEXT NOT NULL,
    CHECK (snapshot_digest IS NULL OR length(snapshot_digest) = 32),
    CHECK (
        (terminal_state = 'SUCCEEDED' AND provider_call_disposition = 'CONFIRMED' AND snapshot_digest IS NOT NULL)
        OR (terminal_state <> 'SUCCEEDED')
    )
);

CREATE TABLE session_selections (
    selection_id TEXT NOT NULL UNIQUE,
    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id),
    terminal_id TEXT NOT NULL UNIQUE REFERENCES terminals(terminal_id),
    selection_schema INTEGER NOT NULL CHECK (selection_schema > 0),
    selection_policy_version TEXT NOT NULL,
    snapshot_digest BLOB NOT NULL CHECK (length(snapshot_digest) = 32),
    selection_evidence_json BLOB NOT NULL,
    selection_evidence_digest BLOB NOT NULL CHECK (length(selection_evidence_digest) = 32),
    selected_at_utc TEXT NOT NULL
);

CREATE TABLE manual_recoveries (
    recovery_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    recovery_ordinal INTEGER NOT NULL CHECK (recovery_ordinal >= 0),
    target_kind TEXT NOT NULL CHECK (target_kind IN (
        'SESSION', 'ATTEMPT', 'CLAIM', 'LAUNCH_RESERVATION', 'TERMINAL'
    )),
    target_id TEXT NOT NULL CHECK (length(target_id) > 0),
    action TEXT NOT NULL,
    predecessor_state TEXT NOT NULL,
    resulting_state TEXT NOT NULL,
    recovery_schema INTEGER NOT NULL CHECK (recovery_schema > 0),
    recovery_policy_version TEXT NOT NULL,
    operator_evidence_json BLOB NOT NULL,
    operator_evidence_digest BLOB NOT NULL CHECK (length(operator_evidence_digest) = 32),
    created_at_utc TEXT NOT NULL,
    UNIQUE (session_id, recovery_ordinal)
);

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

CREATE TRIGGER schema_migrations_no_delete
BEFORE DELETE ON schema_migrations
BEGIN
    SELECT RAISE(ABORT, 'schema migrations cannot be deleted');
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
    OR (OLD.state = 'OPEN' AND NEW.state IN ('SUCCESS_SELECTED', 'CLOSED'))
    OR (OLD.state = 'SUCCESS_SELECTED' AND NEW.state = 'CLOSED')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid session state transition');
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
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM sessions
        WHERE session_id = NEW.session_id AND state = 'OPEN'
    ) THEN RAISE(ABORT, 'attempt session is not open') END;
    SELECT CASE WHEN NEW.ordinal <> (
        SELECT next_attempt_ordinal FROM sessions WHERE session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'attempt ordinal is not the session counter') END;
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
    OR (OLD.state = 'ALLOCATED' AND NEW.state = 'CLAIM_COMMITTED')
    OR (OLD.state = 'CLAIM_COMMITTED' AND NEW.state = 'LAUNCH_RESERVED')
    OR (OLD.state = 'LAUNCH_RESERVED' AND NEW.state IN ('LAUNCH_MAY_HAVE_OCCURRED', 'TERMINAL_RECORDED'))
    OR (OLD.state = 'LAUNCH_MAY_HAVE_OCCURRED' AND NEW.state = 'TERMINAL_RECORDED')
    OR (OLD.state = 'TERMINAL_RECORDED' AND NEW.state IN ('SUCCESS_SELECTED', 'CLOSED'))
    OR (OLD.state = 'SUCCESS_SELECTED' AND NEW.state = 'CLOSED')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid attempt state transition');
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

CREATE TRIGGER launch_reservations_state_guard
BEFORE UPDATE OF reservation_state ON launch_reservations
WHEN NOT (
    NEW.reservation_state = OLD.reservation_state
    OR (OLD.reservation_state = 'COMMITTED' AND NEW.reservation_state IN ('PROCESS_CREATED', 'PROCESS_CREATION_FAILED', 'MANUAL_REVIEW'))
    OR (OLD.reservation_state IN ('PROCESS_CREATED', 'PROCESS_CREATION_FAILED', 'MANUAL_REVIEW') AND NEW.reservation_state = 'TERMINAL_RECORDED')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid launch reservation state transition');
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
    OR (OLD.phase = 'PRE_RESUME_READY' AND NEW.phase IN ('RESUME_RECORDED', 'POST_RESUME_AMBIGUOUS'))
    OR (OLD.phase = 'RESUME_RECORDED' AND NEW.phase IN ('POST_RESUME_AMBIGUOUS', 'TERMINAL_RECORDED'))
    OR (OLD.phase = 'POST_RESUME_AMBIGUOUS' AND NEW.phase IN ('TERMINAL_RECORDED', 'CLOSED'))
    OR (OLD.phase = 'TERMINAL_RECORDED' AND NEW.phase = 'CLOSED')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid launch execution phase transition');
END;

CREATE TRIGGER launch_executions_no_delete
BEFORE DELETE ON launch_executions
BEGIN
    SELECT RAISE(ABORT, 'launch executions cannot be deleted');
END;

CREATE TRIGGER terminals_no_update
BEFORE UPDATE ON terminals
BEGIN
    SELECT RAISE(ABORT, 'terminals are immutable');
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
          AND t.terminal_state = 'SUCCEEDED'
          AND t.provider_call_disposition = 'CONFIRMED'
          AND t.snapshot_digest IS NEW.snapshot_digest
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
    SELECT CASE WHEN NEW.recovery_ordinal <> (
        SELECT next_recovery_ordinal FROM sessions WHERE session_id = NEW.session_id
    ) THEN RAISE(ABORT, 'recovery ordinal is not the session counter') END;
    SELECT CASE WHEN NEW.predecessor_state = NEW.resulting_state
        THEN RAISE(ABORT, 'recovery state transition is empty') END;
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
