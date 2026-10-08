-- Where an orchestrator run's time went, one row per component build and per test leg (entry);
-- run-level columns repeat on each row. Executor-neutral: a GHA workflow and a Jenkins-local
-- `make test` fill the same provision/exec columns. *_ms are derived here, NULL when an end is unknown.
CREATE TABLE IF NOT EXISTS ci_run_timings
(
    -- The orchestrator's "<JOB_NAME>#<BUILD_NUMBER>", the same string as pipeline_runs.run_key.
    run_key                String,
    updated_at             DateTime64(3, 'UTC'),
    entry                  LowCardinality(String),
    component              LowCardinality(String),
    artifact_name          String,
    arch                   LowCardinality(String),
    id12                   String DEFAULT '',
    kind                   LowCardinality(String) DEFAULT 'image',
    -- A test leg's modes, sorted by the writer; '' key for a build entry.
    test_modes             Array(LowCardinality(String)),
    leg                    String MATERIALIZED arrayStringConcat(test_modes, ','),
    -- A retried build or re-dispatched leg is its own row, so a flaky first attempt stays visible.
    attempt                UInt16 DEFAULT 1,

    -- The run, as on its pipeline_runs row; trigger_pr is '' for a non-PR run.
    trigger_kind           LowCardinality(String) DEFAULT '',
    trigger_source         LowCardinality(String) DEFAULT '',
    preset                 LowCardinality(String) DEFAULT '',
    build_mode             LowCardinality(String) DEFAULT '',
    trigger_pr             String DEFAULT '',
    repo                   LowCardinality(String) DEFAULT '',
    pr_number              UInt32 DEFAULT 0,
    sha                    String DEFAULT '',
    -- The component is one of the run's PRs (trigger or Test-With companion), not a dependency.
    is_pr_component        Bool DEFAULT false,
    build_url              String DEFAULT '',
    verdict                LowCardinality(String) DEFAULT '',
    run_result             LowCardinality(String) DEFAULT '',
    superseded             Bool DEFAULT false,
    pickup_path            LowCardinality(String) DEFAULT '',
    comment_at             Nullable(DateTime64(3, 'UTC')),
    picked_up_at           Nullable(DateTime64(3, 'UTC')),
    run_scheduled_at       Nullable(DateTime64(3, 'UTC')),
    -- Not Nullable: it is the partition key, and a replaced row must land in the same partition.
    run_started_at         DateTime64(3, 'UTC'),
    pr_queued_at           Nullable(DateTime64(3, 'UTC')),
    pr_running_at          Nullable(DateTime64(3, 'UTC')),
    run_ended_at           Nullable(DateTime64(3, 'UTC')),

    -- The entry. build: built/reused (concurrent build)/dropped (already published)/failed;
    -- test: passed/failed/error (no test signal). result is the Jenkins result, lowercased.
    state                  LowCardinality(String) DEFAULT '',
    result                 LowCardinality(String) DEFAULT '',
    gating                 LowCardinality(String) DEFAULT '',
    url                    String DEFAULT '',
    agent                  LowCardinality(String) DEFAULT '',
    -- build: component-build start, agent and build lock held, test stage start or job end.
    -- test: dispatched, leg's test stage start, leg job end.
    queued_at              Nullable(DateTime64(3, 'UTC')),
    started_at             Nullable(DateTime64(3, 'UTC')),
    ended_at               Nullable(DateTime64(3, 'UTC')),

    -- The test executor. provision: ARC runner-set deploy, or the card lock wait (jenkins-local, jenkins-job).
    -- exec: workflow dispatch -> first job start -> last job end, or `make test` start -> end.
    executor               LowCardinality(String) DEFAULT '',
    provision_started_at   Nullable(DateTime64(3, 'UTC')),
    provision_ended_at     Nullable(DateTime64(3, 'UTC')),
    exec_dispatched_at     Nullable(DateTime64(3, 'UTC')),
    exec_started_at        Nullable(DateTime64(3, 'UTC')),
    exec_ended_at          Nullable(DateTime64(3, 'UTC')),
    exec_runs              UInt16 DEFAULT 0,
    exec_jobs              UInt32 DEFAULT 0,
    exec_result            LowCardinality(String) DEFAULT '',
    exec_urls              Array(String),
    -- GHA: the gha:<owner>/<repo>/<run_id>#<attempt> pipeline_runs keys, for per-job runner waits.
    exec_run_keys          Array(String),
    cards                  Array(LowCardinality(String)),
    runner_died            Bool DEFAULT false,
    failure_reason         LowCardinality(String) DEFAULT '',
    failed_stage           String DEFAULT '',

    -- Derived. A cross-clock span (Jenkins ms vs GitHub s) can come out negative; it is stored as 0.
    -- if(d < 0, 0, d), not greatest(0, d): greatest returns 0 for a NULL end, this keeps the NULL.
    comment_to_pickup_ms   Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', comment_at, picked_up_at) < 0, 0, dateDiff('millisecond', comment_at, picked_up_at)) AS Nullable(UInt64)),
    comment_to_queued_ms   Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', comment_at, pr_queued_at) < 0, 0, dateDiff('millisecond', comment_at, pr_queued_at)) AS Nullable(UInt64)),
    queued_to_running_ms   Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', pr_queued_at, pr_running_at) < 0, 0, dateDiff('millisecond', pr_queued_at, pr_running_at)) AS Nullable(UInt64)),
    comment_to_end_ms      Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', comment_at, run_ended_at) < 0, 0, dateDiff('millisecond', comment_at, run_ended_at)) AS Nullable(UInt64)),
    run_ms                 Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', run_started_at, run_ended_at) < 0, 0, dateDiff('millisecond', run_started_at, run_ended_at)) AS Nullable(UInt64)),
    queue_ms               Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', queued_at, started_at) < 0, 0, dateDiff('millisecond', queued_at, started_at)) AS Nullable(UInt64)),
    duration_ms            Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', started_at, ended_at) < 0, 0, dateDiff('millisecond', started_at, ended_at)) AS Nullable(UInt64)),
    provision_ms           Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', provision_started_at, provision_ended_at) < 0, 0, dateDiff('millisecond', provision_started_at, provision_ended_at)) AS Nullable(UInt64)),
    exec_queue_ms          Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', exec_dispatched_at, exec_started_at) < 0, 0, dateDiff('millisecond', exec_dispatched_at, exec_started_at)) AS Nullable(UInt64)),
    exec_ms                Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', exec_started_at, exec_ended_at) < 0, 0, dateDiff('millisecond', exec_started_at, exec_ended_at)) AS Nullable(UInt64)),
    teardown_ms            Nullable(UInt64) MATERIALIZED CAST(if(dateDiff('millisecond', exec_ended_at, ended_at) < 0, 0, dateDiff('millisecond', exec_ended_at, ended_at)) AS Nullable(UInt64)),

    props                  Map(LowCardinality(String), String),
    audit_uuid             UUID DEFAULT generateUUIDv7(),
    audit_timestamp        DateTime64(3) DEFAULT now64(3),

    CONSTRAINT chk_timing_entry CHECK entry IN ('build', 'test'),
    CONSTRAINT chk_timing_state CHECK (entry = 'build' AND state IN ('built', 'reused', 'dropped', 'failed', ''))
                                   OR (entry = 'test' AND state IN ('passed', 'failed', 'error', '')),
    CONSTRAINT chk_timing_executor CHECK executor IN ('gha-ephemeral', 'gha-standing', 'jenkins-local', 'jenkins-job', '')
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(run_started_at)
ORDER BY (run_key, entry, component, artifact_name, arch, leg, attempt);
