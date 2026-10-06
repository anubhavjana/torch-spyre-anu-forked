-- Views spanning both families, hence neither 50- nor 51-: v_run_coverage joins
-- artifact_results to test_case_runs to ask "did the leg that produced this artifact actually
-- report cases". Apply last -- it needs every table above.

-- Coverage honesty: artifact_results is a sparse junction, so a chart drawn from it is a
-- sample, not a census, and this view lets the UI label that rather than hide it. Grain is
-- (day, arch), since coverage varies by platform and over time. Both gaps are reported since
-- they differ: cases with no junction row are invisible to every artifact page, while a
-- junction row with no cases is a suite that never reported (a silent zero otherwise).
-- A smoke-only run is an import probe that writes no JUnit by design, so it is counted apart
-- (runs_no_case_output) and left out of both runs_missing_cases and the coverage denominator.
CREATE VIEW IF NOT EXISTS v_run_coverage AS
SELECT
    day,
    arch,
    uniqExact(run_id)                              AS runs,
    uniqExactIf(run_id, in_results AND in_cases)   AS runs_linked,
    uniqExactIf(run_id, NOT in_results)            AS runs_missing_result,
    uniqExactIf(run_id, NOT in_cases AND NOT smoke_only) AS runs_missing_cases,
    uniqExactIf(run_id, NOT in_cases AND smoke_only)     AS runs_no_case_output,
    runs_linked / nullIf(runs - runs_no_case_output, 0) AS coverage
FROM
(
    -- Every run known from either side: a run in only one table is the gap being measured, so
    -- neither table alone can enumerate the denominator.
    SELECT
        min(day)   AS day,
        argMax(arch, arch != '') AS arch,
        run_id,
        max(in_results) AS in_results,
        max(in_cases)   AS in_cases,
        in_results AND NOT max(non_smoke) AS smoke_only
    FROM
    (
        -- state='running' excluded: a crashed run's stale row would count as covered.
        SELECT toDate(ts) AS day, if(arch IN ('amd64', 'x86', 'x86-64'), 'x86_64', arch) AS arch,
               run_id, 1 AS in_results, 0 AS in_cases, test_type != 'smoke' AS non_smoke
        FROM artifact_results
        WHERE state != 'running'
        UNION ALL
        SELECT toDate(min(ts)) AS day, '' AS arch, run_id, 0 AS in_results, 1 AS in_cases,
               0 AS non_smoke
        FROM test_case_runs
        GROUP BY run_id
    )
    GROUP BY run_id
)
GROUP BY day, arch;

-- Latest outcome per test across every run of a tagged artifact; always filter by tag.
CREATE VIEW IF NOT EXISTS v_tag_case_latest AS
SELECT
    tag,
    tag_family,
    component,
    artifact_arch,
    artifact_id,
    test_type,
    run_arch,
    case_component,
    classname,
    name,
    argMax(o, (rts, rid)).1  AS status,
    argMax(o, (rts, rid)).2  AS duration_s,
    argMax(o, (rts, rid)).3  AS fail_message,
    argMax(rid, (rts, rid))  AS run_id,
    max(rts)                 AS run_ts,
    count()                  AS runs
FROM
(
    -- One row per (run, case): the worst outcome when a run's shard files disagree.
    SELECT
        leg.tag         AS tag,
        leg.tag_family  AS tag_family,
        leg.component   AS component,
        leg.artifact_arch AS artifact_arch,
        leg.artifact_id AS artifact_id,
        leg.test_type   AS test_type,
        leg.run_arch    AS run_arch,
        leg.run_ts      AS rts,
        cr.run_id       AS rid,
        cr.component    AS case_component,
        c.classname     AS classname,
        c.name          AS name,
        argMax((cr.status, cr.duration_s, cr.fail_message),
               indexOf(['skipped', 'xfail', 'passed', 'xpass', 'failed', 'error'], cr.status)) AS o
    FROM test_case_runs AS cr
    INNER JOIN
    (
        SELECT
            tr.tag         AS tag,
            tr.tag_family  AS tag_family,
            tr.component   AS component,
            tr.arch        AS artifact_arch,
            tr.artifact_id AS artifact_id,
            r.run_id       AS run_id,
            argMax(r.test_type, r.ts) AS test_type,
            argMax(if(r.arch IN ('amd64', 'x86', 'x86-64'), 'x86_64', r.arch), r.ts) AS run_arch,
            min(r.ts)      AS run_ts
        FROM v_tag_resolution AS tr
        INNER JOIN artifact_results AS r ON r.artifact_id = tr.artifact_id
        WHERE r.state != 'running' AND r.result_kind = 'functional'
        GROUP BY tag, tag_family, component, artifact_arch, artifact_id, run_id
    ) AS leg ON leg.run_id = cr.run_id
    LEFT JOIN test_cases AS c
           ON c.test_case_id = cr.test_case_id AND c.component = cr.component
    GROUP BY tag, tag_family, component, artifact_arch, artifact_id, test_type, run_arch,
             rts, rid, case_component, classname, name
)
GROUP BY tag, tag_family, component, artifact_arch, artifact_id, test_type, run_arch,
         case_component, classname, name;
