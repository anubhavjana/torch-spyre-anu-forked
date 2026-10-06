-- RERUNNABLE
-- Recounts runs whose run_case_counters drifted from test_case_runs; run while no ingest writes.

DROP TABLE IF EXISTS counter_drift_runs;

CREATE TABLE counter_drift_runs (run_id UUID) ENGINE = MergeTree ORDER BY run_id;

INSERT INTO counter_drift_runs
SELECT DISTINCT run_id
FROM
(
    SELECT run_id, component,
           toInt64(count())                     AS t,
           toInt64(countIf(status = 'passed'))  AS p,
           toInt64(countIf(status = 'failed'))  AS f,
           toInt64(countIf(status = 'error'))   AS e,
           toInt64(countIf(status = 'skipped')) AS s,
           toInt64(countIf(status = 'xfail'))   AS xf,
           toInt64(countIf(status = 'xpass'))   AS xp
    FROM test_case_runs
    GROUP BY run_id, component
    UNION ALL
    SELECT run_id, component,
           -toInt64(sum(total_tests)), -toInt64(sum(passed)), -toInt64(sum(failed)),
           -toInt64(sum(errors)), -toInt64(sum(skipped)), -toInt64(sum(xfail)), -toInt64(sum(xpass))
    FROM run_case_counters
    GROUP BY run_id, component
)
GROUP BY run_id, component
HAVING sum(t) != 0 OR sum(p) != 0 OR sum(f) != 0 OR sum(e) != 0
    OR sum(s) != 0 OR sum(xf) != 0 OR sum(xp) != 0;

DELETE FROM run_case_counters WHERE run_id IN (SELECT run_id FROM counter_drift_runs);

INSERT INTO run_case_counters
SELECT
    run_id,
    component,
    count(),
    countIf(status = 'passed'),
    countIf(status = 'failed'),
    countIf(status = 'error'),
    countIf(status = 'skipped'),
    countIf(status = 'xfail'),
    countIf(status = 'xpass')
FROM test_case_runs
WHERE run_id IN (SELECT run_id FROM counter_drift_runs)
GROUP BY run_id, component;

DROP TABLE counter_drift_runs;
