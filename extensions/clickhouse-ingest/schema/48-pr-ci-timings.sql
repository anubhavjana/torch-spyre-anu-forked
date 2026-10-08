-- Per-PR CI timeline, one row per component artifact and arch of a PR-triggered run; *_ms are derived and NULL when unknown.
CREATE TABLE IF NOT EXISTS pr_ci_timings
(
    -- The orchestrator's "<JOB_NAME>#<BUILD_NUMBER>", the same string as pipeline_runs.run_key.
    run_key                  String,
    updated_at               DateTime64(3, 'UTC'),
    component                LowCardinality(String),
    artifact_name            String,
    arch                     LowCardinality(String),
    id12                     String DEFAULT '',
    kind                     LowCardinality(String) DEFAULT '',

    -- The PR the run is for: "<host>/<owner>/<repo>#<n>", split into repo and pr_number.
    trigger_pr               String,
    repo                     LowCardinality(String),
    pr_number                UInt32,
    -- The row whose component is the PR's own repo, as opposed to a dependency built for it.
    is_trigger_component     Bool DEFAULT false,
    trigger_source           LowCardinality(String) DEFAULT '',
    preset                   LowCardinality(String) DEFAULT '',
    build_url                String DEFAULT '',
    verdict                  LowCardinality(String) DEFAULT '',
    run_result               LowCardinality(String) DEFAULT '',

    -- The run, repeated on each of its rows; queued_at/running_at are the PR comment's first such state.
    pickup_path              LowCardinality(String) DEFAULT '',
    comment_at               Nullable(DateTime64(3, 'UTC')),
    picked_up_at             Nullable(DateTime64(3, 'UTC')),
    run_scheduled_at         Nullable(DateTime64(3, 'UTC')),
    run_started_at           Nullable(DateTime64(3, 'UTC')),
    queued_at                Nullable(DateTime64(3, 'UTC')),
    running_at               Nullable(DateTime64(3, 'UTC')),
    run_ended_at             Nullable(DateTime64(3, 'UTC')),
    comment_to_pickup_ms     Nullable(UInt64),
    comment_to_queued_ms     Nullable(UInt64),
    queued_to_running_ms     Nullable(UInt64),
    comment_to_end_ms        Nullable(UInt64),
    run_ms                   Nullable(UInt64),

    -- The component-build: build_queue_ms waits for an agent and the build lock, build_ms ends at its test stage.
    build_state              LowCardinality(String) DEFAULT '',
    build_job_url            String DEFAULT '',
    build_agent              LowCardinality(String) DEFAULT '',
    build_queued_at          Nullable(DateTime64(3, 'UTC')),
    build_started_at         Nullable(DateTime64(3, 'UTC')),
    build_ended_at           Nullable(DateTime64(3, 'UTC')),
    build_queue_ms           Nullable(UInt64),
    build_ms                 Nullable(UInt64),

    -- The test leg: runner-set deploy, GHA workflow, undeploy; several workflows report the earliest start and latest end.
    test_modes               Array(LowCardinality(String)),
    test_state               LowCardinality(String) DEFAULT '',
    test_dispatched_at       Nullable(DateTime64(3, 'UTC')),
    test_leg_started_at      Nullable(DateTime64(3, 'UTC')),
    runner_deploy_started_at Nullable(DateTime64(3, 'UTC')),
    runner_deploy_ended_at   Nullable(DateTime64(3, 'UTC')),
    gha_dispatched_at        Nullable(DateTime64(3, 'UTC')),
    gha_created_at           Nullable(DateTime64(3, 'UTC')),
    gha_first_job_started_at Nullable(DateTime64(3, 'UTC')),
    gha_completed_at         Nullable(DateTime64(3, 'UTC')),
    test_leg_ended_at        Nullable(DateTime64(3, 'UTC')),
    gha_runs                 UInt16 DEFAULT 0,
    gha_jobs                 UInt32 DEFAULT 0,
    gha_conclusion           LowCardinality(String) DEFAULT '',
    gha_run_urls             Array(String),
    test_leg_queue_ms        Nullable(UInt64),
    runner_deploy_ms         Nullable(UInt64),
    gha_queue_ms             Nullable(UInt64),
    gha_e2e_ms               Nullable(UInt64),
    gha_to_leg_end_ms        Nullable(UInt64),
    test_leg_ms              Nullable(UInt64),

    props                    Map(LowCardinality(String), String),
    audit_uuid               UUID DEFAULT generateUUIDv7(),
    audit_timestamp          DateTime64(3) DEFAULT now64(3),

    CONSTRAINT chk_pr_build_state CHECK build_state IN ('built', 'failed', 'reused', ''),
    CONSTRAINT chk_pr_test_state CHECK test_state IN ('passed', 'failed', 'error', '')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (run_key, component, artifact_name, arch);
